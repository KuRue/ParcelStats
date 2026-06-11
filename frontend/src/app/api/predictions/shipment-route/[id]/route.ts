import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { shipments } from "@/lib/db-schema";
import { auth } from "@/lib/auth";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

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
    return NextResponse.json(result);
  } catch {
    return NextResponse.json(
      { status: "error", message: "Route prediction service unavailable" },
      { status: 502 }
    );
  }
}
