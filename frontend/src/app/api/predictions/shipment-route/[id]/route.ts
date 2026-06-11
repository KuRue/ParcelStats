import { NextResponse } from "next/server";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const result = await mlClient.request(`/predict/route-for-shipment/${params.id}`);
    return NextResponse.json(result);
  } catch {
    return NextResponse.json(
      { status: "error", message: "Route prediction service unavailable" },
      { status: 502 }
    );
  }
}
