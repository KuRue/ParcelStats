import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { shipments, carriers, shipmentEvents, predictions } from "@/lib/db-schema";
import { eq, and, desc } from "drizzle-orm";
import { auth } from "@/lib/auth";

export async function GET(
  _request: Request,
  { params }: { params: { id: string } }
) {
  const session = await auth();
  const shipmentId = params.id;

  const [shipment] = await db
    .select()
    .from(shipments)
    .where(eq(shipments.id, shipmentId))
    .limit(1);

  // Community shipments (no owner) are public; user shipments are owner-only.
  if (
    !shipment ||
    (shipment.userId !== null && shipment.userId !== session?.user?.id)
  ) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const [carrier] = await db
    .select()
    .from(carriers)
    .where(eq(carriers.id, shipment.carrierId))
    .limit(1);

  const events = await db
    .select()
    .from(shipmentEvents)
    .where(eq(shipmentEvents.shipmentId, shipmentId))
    .orderBy(desc(shipmentEvents.eventTime));

  const [prediction] = await db
    .select()
    .from(predictions)
    .where(eq(predictions.shipmentId, shipmentId))
    .orderBy(desc(predictions.createdAt))
    .limit(1);

  return NextResponse.json({
    canDelete: shipment.userId !== null && shipment.userId === session?.user?.id,
    id: shipment.id,
    trackingNumber: shipment.trackingNumber,
    carrier: {
      name: carrier?.name,
      slug: carrier?.slug,
      trackingUrlTemplate: carrier?.trackingUrlTemplate,
    },
    status: shipment.status,
    serviceType: shipment.serviceType,
    originName: shipment.originName,
    originLat: shipment.originLat,
    originLng: shipment.originLng,
    destName: shipment.destName,
    destLat: shipment.destLat,
    destLng: shipment.destLng,
    shippedAt: shipment.shippedAt,
    deliveredAt: shipment.deliveredAt,
    estimatedDelivery: shipment.estimatedDelivery,
    events: events.map((e) => ({
      status: e.status,
      locationName: e.locationName,
      locationLat: e.locationLat,
      locationLng: e.locationLng,
      description: e.description,
      eventTime: e.eventTime,
    })),
    prediction: prediction
      ? {
          predictedDelivery: prediction.predictedDelivery,
          confidenceLow: prediction.confidenceLow,
          confidenceHigh: prediction.confidenceHigh,
          confidencePct: prediction.confidencePct ? parseFloat(prediction.confidencePct) : 0,
          modelVersion: prediction.modelVersion,
        }
      : null,
  });
}

export async function DELETE(
  _request: Request,
  { params }: { params: { id: string } }
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const [deleted] = await db
    .delete(shipments)
    .where(
      and(
        eq(shipments.id, params.id),
        eq(shipments.userId, session.user.id)
      )
    )
    .returning({ id: shipments.id });

  if (!deleted) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  return NextResponse.json({ id: deleted.id, status: "deleted" });
}
