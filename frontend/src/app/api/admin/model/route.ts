import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { predictions } from "@/lib/db-schema";
import { sql, desc } from "drizzle-orm";
import { z } from "zod";
import { requireAdmin } from "@/lib/auth";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await requireAdmin();
  if (!session) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // Which prediction source actually served users: real model versions (vNNN)
  // vs fallback chain (route stats / carrier estimate / baseline).
  const sourceBreakdown = await db
    .select({
      modelVersion: predictions.modelVersion,
      count: sql<number>`count(*)::int`,
      avgConfidence: sql<number>`coalesce(avg(${predictions.confidencePct}), 0)::numeric(5,1)`,
    })
    .from(predictions)
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
  action: z.enum(["retrain", "seed"]),
  count: z.number().int().min(100).max(10000).optional(),
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
    if (parsed.data.action === "retrain") {
      const result = await mlClient.triggerRetrain();
      return NextResponse.json(result);
    }
    const result = await mlClient.seedSyntheticData(parsed.data.count ?? 2000);
    return NextResponse.json(result);
  } catch (error) {
    console.error("Admin model action failed:", error);
    return NextResponse.json(
      { error: "ML service unavailable" },
      { status: 502 }
    );
  }
}
