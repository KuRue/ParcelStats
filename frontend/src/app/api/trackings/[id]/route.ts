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
    .where(
      session?.user?.id
        ? and(eq(shipments.id, shipmentId), eq(shipments.userId, session.user.id))
        : eq(shipments.id, shipmentId)
    )
    .limit(1);

  if (!shipment) {
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
