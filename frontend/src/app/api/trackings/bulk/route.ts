import { NextResponse } from "next/server";
import { and, eq, inArray } from "drizzle-orm";
import { z } from "zod";
import { auth } from "@/lib/auth";
import { db } from "@/lib/db";
import { carriers, shipments } from "@/lib/db-schema";
import {
  isSpeedPakTrackingNumber,
  normalizeTrackingNumber,
} from "@/lib/carrier-detection";
import { internalApiKeyHeader } from "@/lib/ml-client";
import { rateLimit } from "@/lib/rate-limit";

const MAX_BULK_IMPORT = 100;

const bulkImportSchema = z.object({
  trackingNumbers: z.array(z.string().min(1).max(80)).min(1).max(MAX_BULK_IMPORT),
  confirmOwned: z.literal(true),
});

interface ImportIssue {
  trackingNumber: string;
  reason: string;
}

export async function POST(request: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const limited = await rateLimit({
    action: "bulk-import-speedpak",
    key: session.user.id,
    limit: 5,
    windowSeconds: 3600,
  });
  if (limited) return limited;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = bulkImportSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      {
        error:
          parsed.error.issues[0]?.message ||
          "Bulk import requires SpeedPAK numbers and ownership confirmation",
      },
      { status: 400 }
    );
  }

  const invalid: ImportIssue[] = [];
  const duplicates: string[] = [];
  const seen = new Set<string>();
  const validNumbers: string[] = [];

  for (const raw of parsed.data.trackingNumbers) {
    const trackingNumber = normalizeTrackingNumber(raw);
    if (!trackingNumber) continue;
    if (seen.has(trackingNumber)) {
      duplicates.push(trackingNumber);
      continue;
    }
    seen.add(trackingNumber);

    if (!isSpeedPakTrackingNumber(trackingNumber)) {
      invalid.push({
        trackingNumber,
        reason: "Not a recognized SpeedPAK tracking number",
      });
      continue;
    }

    validNumbers.push(trackingNumber);
  }

  if (validNumbers.length === 0) {
    return NextResponse.json(
      {
        error: "No valid SpeedPAK tracking numbers found",
        received: parsed.data.trackingNumbers.length,
        invalid,
        duplicates,
      },
      { status: 400 }
    );
  }

  const [carrier] = await db
    .select()
    .from(carriers)
    .where(eq(carriers.slug, "speedpak"))
    .limit(1);

  if (!carrier) {
    return NextResponse.json({ error: "SpeedPAK carrier not found" }, { status: 404 });
  }

  const existing = await db
    .select({
      trackingNumber: shipments.trackingNumber,
      userId: shipments.userId,
    })
    .from(shipments)
    .where(
      and(
        eq(shipments.carrierId, carrier.id),
        inArray(shipments.trackingNumber, validNumbers)
      )
    );

  const ownedExisting = new Set(
    existing
      .filter((s) => s.userId === session.user.id)
      .map((s) => s.trackingNumber)
  );
  const alreadyInSystem = new Set(existing.map((s) => s.trackingNumber));

  const rowsToInsert = validNumbers
    .filter((trackingNumber) => !alreadyInSystem.has(trackingNumber))
    .map((trackingNumber) => ({
      trackingNumber,
      carrierId: carrier.id,
      userId: session.user.id,
      status: "pending",
      source: "user",
    }));

  const inserted =
    rowsToInsert.length > 0
      ? await db
          .insert(shipments)
          .values(rowsToInsert)
          .onConflictDoNothing()
          .returning({
            id: shipments.id,
            trackingNumber: shipments.trackingNumber,
          })
      : [];

  let queued = 0;
  let queueFailures = 0;
  const mlServiceUrl = process.env.ML_SERVICE_URL;
  if (mlServiceUrl && inserted.length > 0) {
    const results = await Promise.allSettled(
      inserted.map((shipment) =>
        fetch(`${mlServiceUrl}/scrape/trigger`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...internalApiKeyHeader(),
          },
          body: JSON.stringify({
            tracking_number: shipment.trackingNumber,
            carrier_slug: "speedpak",
            shipment_id: shipment.id,
          }),
        })
      )
    );

    for (const result of results) {
      if (result.status === "fulfilled" && result.value.ok) {
        queued += 1;
      } else {
        queueFailures += 1;
      }
    }
  } else {
    queueFailures = inserted.length;
  }

  return NextResponse.json({
    status: "ok",
    received: parsed.data.trackingNumbers.length,
    valid: validNumbers.length,
    imported: inserted.length,
    queued,
    queueFailures,
    duplicates: duplicates.length,
    invalid,
    alreadyTracked: ownedExisting.size,
    alreadyInSystem: alreadyInSystem.size - ownedExisting.size,
    maxImport: MAX_BULK_IMPORT,
  });
}
