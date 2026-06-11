import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { shipments } from "@/lib/db-schema";
import { auth } from "@/lib/auth";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

type MlFutureStop = {
  stop_order?: number;
  location_name?: string;
  location_lat?: number | string | null;
  location_lng?: number | string | null;
  status?: string;
  frequency_pct?: number | string;
  eta?: string;
  median_days_from_start?: number | string;
  p10_days?: number | string;
  p90_days?: number | string;
};

type MlRoutePrediction = {
  status?: string;
  message?: string;
  route?: {
    carrier_slug?: string;
    origin_country?: string;
    dest_country?: string;
    label?: string;
    matched_stops?: number;
    total_pattern_stops?: number;
    total_events?: number;
    score?: number | string;
    sample_count?: number;
    future_stops?: MlFutureStop[];
  };
};

function toNumber(value: number | string | null | undefined): number | null {
  if (value == null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeRoutePrediction(result: MlRoutePrediction) {
  if (result.status !== "ok" || !result.route) {
    return result;
  }

  return {
    status: "ok",
    route: {
      carrierSlug: result.route.carrier_slug ?? "",
      originCountry: result.route.origin_country ?? "",
      destCountry: result.route.dest_country ?? "",
      label: result.route.label ?? "",
      matchedStops: result.route.matched_stops ?? 0,
      totalPatternStops: result.route.total_pattern_stops ?? 0,
      totalEvents: result.route.total_events ?? 0,
      score: toNumber(result.route.score) ?? 0,
      sampleCount: result.route.sample_count ?? 0,
      futureStops: (result.route.future_stops ?? []).map((stop) => ({
        stopOrder: stop.stop_order ?? 0,
        locationName: stop.location_name ?? "Unknown",
        locationLat: toNumber(stop.location_lat),
        locationLng: toNumber(stop.location_lng),
        status: stop.status ?? "in_transit",
        frequencyPct: toNumber(stop.frequency_pct) ?? 100,
        eta: stop.eta ?? "",
        medianDaysFromStart: toNumber(stop.median_days_from_start) ?? 0,
        p10Days: toNumber(stop.p10_days) ?? 0,
        p90Days: toNumber(stop.p90_days) ?? 0,
      })),
    },
  };
}

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
  // Same visibility rules as the shipment detail route: community
  // shipments are public, user shipments are owner-only.
  const session = await auth();
  const [shipment] = await db
    .select({ userId: shipments.userId })
    .from(shipments)
    .where(eq(shipments.id, params.id))
    .limit(1);

  if (
    !shipment ||
    (shipment.userId !== null && shipment.userId !== session?.user?.id)
  ) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  try {
    const result = await mlClient.request(`/predict/route-for-shipment/${params.id}`);
    return NextResponse.json(normalizeRoutePrediction(result));
  } catch {
    return NextResponse.json(
      { status: "error", message: "Route prediction service unavailable" },
      { status: 502 }
    );
  }
}
