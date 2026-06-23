import { NextResponse } from "next/server";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await mlClient.request("/predict/carrier-stats");
    return NextResponse.json(result);
  } catch (error) {
    console.error("Carrier stats error:", error);
    return NextResponse.json({ status: "error", carriers: [] }, { status: 200 });
  }
}
