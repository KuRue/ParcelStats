import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { shipments, carriers, predictions } from "@/lib/db-schema";
import { sql, desc, eq, notInArray } from "drizzle-orm";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

const LEGACY_FALLBACK_MODELS = ["fallback_route_stats", "carrier_estimate", "baseline_eta"];

interface AccuracyBucket {
  count: number;
  mae_days?: number;
  bias_days?: number;
  within_1_day_pct?: number;
  within_2_days_pct?: number;
}

async function fetchAccuracy(): Promise<{
  overall: AccuracyBucket;
  by_carrier: Record<string, AccuracyBucket>;
} | null> {
  try {
    const res = await mlClient.getAccuracy();
    return res?.accuracy ?? null;
  } catch {
    return null;
  }
}

export async function GET() {
  const [totalResult] = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(shipments);

  const [predictionResult] = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(predictions)
    .where(notInArray(predictions.modelVersion, LEGACY_FALLBACK_MODELS));

  const carrierCount = await db
    .select({
      carrierId: shipments.carrierId,
      carrierName: carriers.name,
      carrierSlug: carriers.slug,
      count: sql<number>`count(*)::int`,
    })
    .from(shipments)
    .innerJoin(carriers, eq(shipments.carrierId, carriers.id))
    .groupBy(shipments.carrierId, carriers.name, carriers.slug)
    .orderBy(desc(sql`count(*)`))
    .limit(10);

  const routeStats = await db
    .select({
      route: sql<string>`
        lower(trim(regexp_replace(coalesce(${shipments.originName}, 'unknown'), '^.*,\\s*', '')))
        || ' → ' ||
        lower(trim(regexp_replace(coalesce(${shipments.destName}, 'unknown'), '^.*,\\s*', '')))
      `,
      avgDays: sql<number>`
        avg(extract(epoch from (${shipments.deliveredAt} - ${shipments.shippedAt})) / 86400)::numeric(6,2)
      `,
      sampleCount: sql<number>`count(*)::int`,
    })
    .from(shipments)
    .where(sql`
      ${shipments.source} = 'user'
      and ${shipments.shippedAt} is not null
      and ${shipments.deliveredAt} is not null
      and ${shipments.originName} is not null
      and ${shipments.destName} is not null
    `)
    .groupBy(sql`
      lower(trim(regexp_replace(coalesce(${shipments.originName}, 'unknown'), '^.*,\\s*', ''))),
      lower(trim(regexp_replace(coalesce(${shipments.destName}, 'unknown'), '^.*,\\s*', '')))
    `)
    .orderBy(desc(sql`count(*)`))
    .limit(10);

  const [avgConf] = await db
    .select({
      avg: sql<number>`coalesce(avg(${predictions.confidencePct}), 0)::numeric(5,2)`,
    })
    .from(predictions)
    .where(notInArray(predictions.modelVersion, LEGACY_FALLBACK_MODELS));

  const uniqueCarriers = await db
    .select({ count: sql<number>`count(distinct ${shipments.carrierId})::int` })
    .from(shipments);

  const accuracy = await fetchAccuracy();

  return NextResponse.json({
    accuracy,
    totalShipments: totalResult?.count ?? 0,
    totalCarriers: uniqueCarriers[0]?.count ?? 0,
    totalPredictions: predictionResult?.count ?? 0,
    avgConfidence: avgConf?.avg ?? 0,
    topCarriers: carrierCount.map((c) => ({
      name: c.carrierName,
      slug: c.carrierSlug,
      count: c.count,
      avgDays: 0,
    })),
    routeStats: routeStats.map((r) => ({
      route: r.route,
      avgDays: r.avgDays ? Number(r.avgDays) : 0,
      sampleCount: r.sampleCount,
    })),
  });
}
