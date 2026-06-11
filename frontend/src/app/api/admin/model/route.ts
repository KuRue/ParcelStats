import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { predictions } from "@/lib/db-schema";
import { sql, desc, notInArray } from "drizzle-orm";
import { z } from "zod";
import { requireAdmin } from "@/lib/auth";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

const LEGACY_FALLBACK_MODELS = ["fallback_route_stats", "carrier_estimate", "baseline_eta"];

export async function GET() {
  const session = await requireAdmin();
  if (!session) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // Which trained model versions actually served users.
  const sourceBreakdown = await db
    .select({
      modelVersion: predictions.modelVersion,
      count: sql<number>`count(*)::int`,
      avgConfidence: sql<number>`coalesce(avg(${predictions.confidencePct}), 0)::numeric(5,1)`,
    })
    .from(predictions)
    .where(notInArray(predictions.modelVersion, LEGACY_FALLBACK_MODELS))
    .groupBy(predictions.modelVersion)
    .orderBy(desc(sql`count(*)`));

  let modelStatus = null;
  let accuracy = null;
  try {
    [modelStatus, accuracy] = await Promise.all([
      mlClient.getModelStatus(),
      mlClient.getAccuracy(),
    ]);
  } catch {
    // ML service unreachable
  }

  return NextResponse.json({
    sourceBreakdown,
    models: modelStatus?.models ?? null,
    accuracy: accuracy?.accuracy ?? null,
  });
}

const actionSchema = z.object({
  action: z.enum(["retrain"]),
});

export async function POST(request: Request) {
  const session = await requireAdmin();
  if (!session) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const parsed = actionSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  }

  try {
    const result = await mlClient.triggerRetrain();
    return NextResponse.json(result);
  } catch (error) {
    console.error("Admin model action failed:", error);
    return NextResponse.json(
      { error: "ML service unavailable" },
      { status: 502 }
    );
  }
}
