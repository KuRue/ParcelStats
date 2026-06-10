import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { shipments, carriers, predictions, carrierRoutes } from "@/lib/db-schema";
import { sql, desc, eq } from "drizzle-orm";

export async function GET() {
  const [totalResult] = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(shipments);

  const [predictionResult] = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(predictions);

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
      route: sql<string>`${carrierRoutes.originRegion} || ' → ' || ${carrierRoutes.destRegion}`,
      avgDays: carrierRoutes.avgDays,
      sampleCount: carrierRoutes.sampleCount,
    })
    .from(carrierRoutes)
    .orderBy(desc(carrierRoutes.sampleCount))
    .limit(10);

  const [avgConf] = await db
    .select({
      avg: sql<number>`coalesce(avg(${predictions.confidencePct}), 0)::numeric(5,2)`,
    })
    .from(predictions);

  const uniqueCarriers = await db
    .select({ count: sql<number>`count(distinct ${shipments.carrierId})::int` })
    .from(shipments);

  return NextResponse.json({
    totalShipments: totalResult?.count ?? 0,
    totalCarriers: uniqueCarriers[0]?.count ?? 0,
    totalPredictions: predictionResult?.count ?? 0,
    avgConfidence: parseFloat(avgConf?.avg ?? "0"),
    topCarriers: carrierCount.map((c) => ({
      name: c.carrierName,
      slug: c.carrierSlug,
      count: c.count,
      avgDays: 0,
    })),
    routeStats,
  });
}
