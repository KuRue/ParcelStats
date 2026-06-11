import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { users, shipments, predictions } from "@/lib/db-schema";
import { sql, desc, gte, notInArray } from "drizzle-orm";
import { requireAdmin } from "@/lib/auth";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

const LEGACY_FALLBACK_MODELS = ["fallback_route_stats", "carrier_estimate", "baseline_eta"];

export async function GET() {
  const session = await requireAdmin();
  if (!session) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const weekAgo = new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString();
  const twoWeeksAgo = new Date(Date.now() - 14 * 24 * 3600 * 1000).toISOString();

  const [
    [userTotals],
    [shipmentTotals],
    statusBreakdown,
    sourceBreakdown,
    perDay,
    [predictionTotals],
    topUsers,
  ] = await Promise.all([
    db
      .select({
        total: sql<number>`count(*)::int`,
        newThisWeek: sql<number>`count(*) filter (where ${users.createdAt} > ${weekAgo}::timestamptz)::int`,
      })
      .from(users),
    db
      .select({
        total: sql<number>`count(*)::int`,
        newThisWeek: sql<number>`count(*) filter (where ${shipments.createdAt} > ${weekAgo}::timestamptz)::int`,
        active: sql<number>`count(*) filter (where ${shipments.deliveredAt} is null)::int`,
        delivered: sql<number>`count(*) filter (where ${shipments.deliveredAt} is not null)::int`,
      })
      .from(shipments),
    db
      .select({
        status: shipments.status,
        count: sql<number>`count(*)::int`,
      })
      .from(shipments)
      .groupBy(shipments.status)
      .orderBy(desc(sql`count(*)`)),
    db
      .select({
        source: shipments.source,
        count: sql<number>`count(*)::int`,
      })
      .from(shipments)
      .groupBy(shipments.source),
    db
      .select({
        day: sql<string>`to_char(${shipments.createdAt}, 'YYYY-MM-DD')`,
        count: sql<number>`count(*)::int`,
      })
      .from(shipments)
      .where(gte(shipments.createdAt, sql`${twoWeeksAgo}::timestamptz`))
      .groupBy(sql`to_char(${shipments.createdAt}, 'YYYY-MM-DD')`)
      .orderBy(sql`to_char(${shipments.createdAt}, 'YYYY-MM-DD')`),
    db
      .select({ total: sql<number>`count(*)::int` })
      .from(predictions)
      .where(notInArray(predictions.modelVersion, LEGACY_FALLBACK_MODELS)),
    db
      .select({
        name: users.name,
        email: users.email,
        shipmentCount: sql<number>`count(${shipments.id})::int`,
      })
      .from(users)
      .leftJoin(shipments, sql`${shipments.userId} = ${users.id}`)
      .groupBy(users.id, users.name, users.email)
      .orderBy(desc(sql`count(${shipments.id})`))
      .limit(10),
  ]);

  let mlHealth = null;
  try {
    mlHealth = await mlClient.getHealth();
  } catch {
    // ML service unreachable - report it as down rather than failing the page
  }

  return NextResponse.json({
    users: userTotals,
    shipments: shipmentTotals,
    statusBreakdown,
    sourceBreakdown,
    shipmentsPerDay: perDay,
    predictions: predictionTotals,
    topUsers,
    mlHealth,
  });
}
