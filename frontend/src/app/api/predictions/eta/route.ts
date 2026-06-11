import { NextResponse } from "next/server";
import { z } from "zod";
import { mlClient } from "@/lib/ml-client";

export const dynamic = "force-dynamic";

const requestSchema = z.object({
  trackingNumber: z.string().min(1),
  carrierSlug: z.string().min(1),
  originRegion: z.string().optional(),
  destRegion: z.string().optional(),
  serviceType: z.string().optional(),
});

export async function POST(request: Request) {
  const parsed = requestSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid request", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const { trackingNumber, carrierSlug, originRegion, destRegion, serviceType } = parsed.data;

  try {
    const result = await mlClient.predictEta({
      trackingNumber,
      carrierSlug,
      originRegion,
      destRegion,
      serviceType,
    });
    return NextResponse.json(result);
  } catch {
    return NextResponse.json(
      { status: "error", message: "Prediction service unavailable" },
      { status: 502 }
    );
  }
}
