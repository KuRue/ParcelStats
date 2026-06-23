import { NextRequest, NextResponse } from "next/server";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const originLat = searchParams.get("origin_lat");
  const originLng = searchParams.get("origin_lng");
  const destLat = searchParams.get("dest_lat");
  const destLng = searchParams.get("dest_lng");

  if (!originLat || !originLng || !destLat || !destLng) {
    return NextResponse.json(
      { error: "origin_lat, origin_lng, dest_lat, dest_lng are required" },
      { status: 400 }
    );
  }

  try {
    const result = await mlClient.request(
      `/flights/route?origin_lat=${originLat}&origin_lng=${originLng}&dest_lat=${destLat}&dest_lng=${destLng}`
    );
    return NextResponse.json(result);
  } catch (error) {
    console.error("Flight lookup error:", error);
    return NextResponse.json(
      { status: "error", count: 0, flights: [] },
      { status: 200 }
    );
  }
}
