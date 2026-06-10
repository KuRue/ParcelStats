import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { shipments, carriers, shipmentEvents, predictions } from "@/lib/db-schema";
import { eq, and, desc } from "drizzle-orm";
import { auth } from "@/lib/auth";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const userShipments = await db
    .select({
      id: shipments.id,
      trackingNumber: shipments.trackingNumber,
      status: shipments.status,
      estimatedDelivery: shipments.estimatedDelivery,
      updatedAt: shipments.updatedAt,
      carrier: {
        name: carriers.name,
        slug: carriers.slug,
      },
    })
    .from(shipments)
    .innerJoin(carriers, eq(shipments.carrierId, carriers.id))
    .where(eq(shipments.userId, session.user.id))
    .orderBy(desc(shipments.updatedAt));

  const enriched = await Promise.all(
    userShipments.map(async (s) => {
      const [lastEvent] = await db
        .select({
          description: shipmentEvents.description,
          locationName: shipmentEvents.locationName,
        })
        .from(shipmentEvents)
        .where(eq(shipmentEvents.shipmentId, s.id))
        .orderBy(desc(shipmentEvents.eventTime))
        .limit(1);

      const [prediction] = await db
        .select({
          confidencePct: predictions.confidencePct,
        })
        .from(predictions)
        .where(eq(predictions.shipmentId, s.id))
        .orderBy(desc(predictions.createdAt))
        .limit(1);

      return {
        ...s,
        lastEvent: lastEvent?.description || null,
        lastLocation: lastEvent?.locationName || null,
        confidencePct: prediction?.confidencePct ? parseFloat(prediction.confidencePct) : null,
      };
    })
  );

  return NextResponse.json(enriched);
}

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { trackingNumber, carrierSlug } = body;

  if (!trackingNumber || !carrierSlug) {
    return NextResponse.json(
      { error: "trackingNumber and carrierSlug required" },
      { status: 400 }
    );
  }

  const [carrier] = await db
    .select()
    .from(carriers)
    .where(eq(carriers.slug, carrierSlug))
    .limit(1);

  if (!carrier) {
    return NextResponse.json({ error: "Carrier not found" }, { status: 404 });
  }

  const [existing] = await db
    .select()
    .from(shipments)
    .where(
      and(
        eq(shipments.trackingNumber, trackingNumber),
        eq(shipments.carrierId, carrier.id),
        eq(shipments.userId, session.user.id)
      )
    )
    .limit(1);

  if (existing) {
    return NextResponse.json({ id: existing.id, status: "already_tracked" });
  }

  const [newShipment] = await db
    .insert(shipments)
    .values({
      trackingNumber,
      carrierId: carrier.id,
      userId: session.user.id,
      status: "pending",
    })
    .returning({ id: shipments.id });

  try {
    await fetch(`${process.env.ML_SERVICE_URL}/scrape/trigger`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        trackingNumber,
        carrierSlug,
        shipmentId: newShipment.id,
      }),
    });
  } catch {}

  return NextResponse.json({ id: newShipment.id, status: "created" });
}
