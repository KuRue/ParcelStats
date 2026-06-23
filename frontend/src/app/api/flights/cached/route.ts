import { NextResponse } from "next/server";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await mlClient.request("/flights/cached");
    return NextResponse.json(result);
  } catch {
    return NextResponse.json({ status: "error", count: 0, flights: [] });
  }
}
