import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { shipments, carriers, shipmentEvents, predictions } from "@/lib/db-schema";
import { eq, and, desc } from "drizzle-orm";
import { z } from "zod";
import { auth } from "@/lib/auth";
import { detectCarrierSlug, normalizeTrackingNumber } from "@/lib/carrier-detection";
import { internalApiKeyHeader } from "@/lib/ml-client";
import { rateLimit } from "@/lib/rate-limit";

function isUniqueViolation(error: unknown) {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as { code?: string }).code === "23505"
  );
}

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const latestEvents = db
    .selectDistinctOn([shipmentEvents.shipmentId], {
      shipmentId: shipmentEvents.shipmentId,
      description: shipmentEvents.description,
      locationName: shipmentEvents.locationName,
      locationLat: shipmentEvents.locationLat,
      locationLng: shipmentEvents.locationLng,
    })
    .from(shipmentEvents)
    .orderBy(shipmentEvents.shipmentId, desc(shipmentEvents.eventTime))
    .as("latest_events");

  const latestPredictions = db
    .selectDistinctOn([predictions.shipmentId], {
      shipmentId: predictions.shipmentId,
      predictedDelivery: predictions.predictedDelivery,
      confidencePct: predictions.confidencePct,
    })
    .from(predictions)
    .orderBy(predictions.shipmentId, desc(predictions.createdAt))
    .as("latest_predictions");

  const rows = await db
    .select({
      id: shipments.id,
      trackingNumber: shipments.trackingNumber,
      status: shipments.status,
      estimatedDelivery: shipments.estimatedDelivery,
      updatedAt: shipments.updatedAt,
      originName: shipments.originName,
      originLat: shipments.originLat,
      originLng: shipments.originLng,
      destName: shipments.destName,
      destLat: shipments.destLat,
      destLng: shipments.destLng,
      carrier: {
        name: carriers.name,
        slug: carriers.slug,
      },
      lastEvent: latestEvents.description,
      lastLocation: latestEvents.locationName,
      lastLat: latestEvents.locationLat,
      lastLng: latestEvents.locationLng,
      predictedDelivery: latestPredictions.predictedDelivery,
      confidencePct: latestPredictions.confidencePct,
    })
    .from(shipments)
    .innerJoin(carriers, eq(shipments.carrierId, carriers.id))
    .leftJoin(latestEvents, eq(latestEvents.shipmentId, shipments.id))
    .leftJoin(latestPredictions, eq(latestPredictions.shipmentId, shipments.id))
    .where(eq(shipments.userId, session.user.id))
    .orderBy(desc(shipments.updatedAt));

  const enriched = rows.map(({ predictedDelivery, confidencePct, ...s }) => ({
    ...s,
    estimatedDelivery: s.estimatedDelivery ?? predictedDelivery ?? null,
    lastEvent: s.lastEvent || null,
    lastLocation: s.lastLocation || null,
    lastLat: s.lastLat || null,
    lastLng: s.lastLng || null,
    confidencePct: confidencePct ? parseFloat(confidencePct) : null,
  }));

  return NextResponse.json(enriched);
}

const createTrackingSchema = z.object({
  trackingNumber: z
    .string()
    .transform(normalizeTrackingNumber)
    .pipe(
      z
        .string()
        .min(6, "Tracking number too short")
        .max(40, "Tracking number too long")
        .regex(/^[0-9A-Z-]+$/, "Tracking number contains invalid characters")
    ),
  carrierSlug: z
    .string()
    .regex(/^[a-z0-9-]{1,50}$/)
    .optional()
    .or(z.literal("auto"))
    .optional(),
});

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const limited = await rateLimit({
    action: "create-tracking",
    key: session.user.id,
    limit: 30,
    windowSeconds: 3600,
  });
  if (limited) return limited;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = createTrackingSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message || "Invalid input" },
      { status: 400 }
    );
  }

  const trackingNumber = parsed.data.trackingNumber;
  const requestedCarrierSlug = parsed.data.carrierSlug ?? "";
  const carrierSlug =
    requestedCarrierSlug && requestedCarrierSlug !== "auto"
      ? requestedCarrierSlug
      : detectCarrierSlug(trackingNumber);

  if (!carrierSlug) {
    return NextResponse.json(
      { error: "Carrier could not be detected" },
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

  let newShipment: { id: string };
  try {
    [newShipment] = await db
      .insert(shipments)
      .values({
        trackingNumber,
        carrierId: carrier.id,
        userId: session.user.id,
        status: "pending",
      })
      .returning({ id: shipments.id });
  } catch (error) {
    if (isUniqueViolation(error)) {
      return NextResponse.json(
        { error: "This tracking number is already tracked for that carrier" },
        { status: 409 }
      );
    }
    throw error;
  }

  try {
    await fetch(`${process.env.ML_SERVICE_URL}/scrape/trigger`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...internalApiKeyHeader(),
      },
      body: JSON.stringify({
        tracking_number: trackingNumber,
        carrier_slug: carrierSlug,
        shipment_id: newShipment.id,
      }),
    });
  } catch (error) {
    console.error("Failed to trigger scrape for new shipment:", error);
  }

  return NextResponse.json({ id: newShipment.id, status: "created" });
}
