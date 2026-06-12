import { NextRequest, NextResponse } from "next/server";
import { mlClient } from "@/lib/ml-client";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { trackingNumber, shipmentId, rawData } = body;

    if (!trackingNumber || !shipmentId || !rawData) {
      return NextResponse.json(
        { error: "trackingNumber, shipmentId, and rawData are required" },
        { status: 400 }
      );
    }

    const result = await mlClient.submitClientFetch(trackingNumber, shipmentId, rawData);
    return NextResponse.json(result);
  } catch (error) {
    console.error("UPS client fetch proxy error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    );
  }
}
