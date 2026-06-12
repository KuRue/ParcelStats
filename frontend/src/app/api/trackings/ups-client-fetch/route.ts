import { NextRequest, NextResponse } from "next/server";
import { mlClient } from "@/lib/ml-client";

async function fetchUPS(trackingNumber: string) {
  const resp = await fetch(
    "https://webapis.ups.com/track/api/Track/GetStatus",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
      },
      body: JSON.stringify({
        Locale: "en_US",
        Requester: "ST/track.web",
        TrackingNumber: [trackingNumber],
      }),
      signal: AbortSignal.timeout(15000),
    }
  );

  if (!resp.ok) return null;

  const ct = resp.headers.get("content-type") || "";
  if (!ct.includes("json")) return null;

  return resp.json();
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { trackingNumber, shipmentId } = body;

    if (!trackingNumber || !shipmentId) {
      return NextResponse.json(
        { error: "trackingNumber and shipmentId are required" },
        { status: 400 }
      );
    }

    const rawData = await fetchUPS(trackingNumber);

    if (!rawData) {
      return NextResponse.json(
        { status: "fetch_failed", events: 0 },
        { status: 200 }
      );
    }

    const result = await mlClient.submitClientFetch(
      trackingNumber,
      shipmentId,
      rawData
    );
    return NextResponse.json(result);
  } catch (error) {
    console.error("UPS proxy fetch error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    );
  }
}
