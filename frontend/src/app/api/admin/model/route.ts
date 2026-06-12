import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { predictions } from "@/lib/db-schema";
import { sql, desc, notInArray } from "drizzle-orm";
import { z } from "zod";
import { requireAdmin } from "@/lib/auth";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

const LEGACY_FALLBACK_MODELS = ["fallback_route_stats", "carrier_estimate", "baseline_eta"];

const actionSchema = z.object({
  action: z.enum(["retrain", "research-missing", "research-active", "research-lane"]),
  carrierSlug: z.string().optional(),
  originCountry: z.string().optional(),
  destCountry: z.string().optional(),
});

export async function GET() {
  const session = await requireAdmin();
  if (!session) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const [sourceBreakdown, modelStatus, accuracy, researchStatus] = await Promise.all([
    db
      .select({
        modelVersion: predictions.modelVersion,
        count: sql<number>`count(*)::int`,
        avgConfidence: sql<number>`coalesce(avg(${predictions.confidencePct}), 0)::numeric(5,1)`,
      })
      .from(predictions)
      .where(notInArray(predictions.modelVersion, LEGACY_FALLBACK_MODELS))
      .groupBy(predictions.modelVersion)
      .orderBy(desc(sql`count(*)`)),
    mlClient.getModelStatus().catch(() => null),
    mlClient.getAccuracy().catch(() => null),
    mlClient.request("/train/research-status").catch(() => null),
  ]);

  return NextResponse.json({
    sourceBreakdown,
    models: modelStatus?.models ?? null,
    accuracy: accuracy?.accuracy ?? null,
    research: researchStatus,
  });
}

export async function POST(request: Request) {
  const session = await requireAdmin();
  if (!session) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const parsed = actionSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  }

  const { action, carrierSlug, originCountry, destCountry } = parsed.data;

  try {
    let result;
    if (action === "retrain") {
      result = await mlClient.triggerRetrain();
    } else if (action === "research-missing") {
      result = await mlClient.request("/train/research-missing", { method: "POST" });
    } else if (action === "research-active") {
      result = await mlClient.request("/train/research-active", { method: "POST" });
    } else if (action === "research-lane") {
      result = await mlClient.request("/train/research-lane", {
        method: "POST",
        body: JSON.stringify({
          carrier_slug: carrierSlug,
          origin_country: originCountry,
          dest_country: destCountry,
        }),
      });
    }
    return NextResponse.json(result ?? { status: "ok" });
  } catch (error) {
    console.error("Admin model action failed:", error);
    return NextResponse.json(
      { error: "ML service unavailable" },
      { status: 502 }
    );
  }
}
