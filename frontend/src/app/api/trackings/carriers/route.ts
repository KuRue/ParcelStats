import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { carriers } from "@/lib/db-schema";

export const dynamic = "force-dynamic";

export async function GET() {
  const allCarriers = await db
    .select({ name: carriers.name, slug: carriers.slug })
    .from(carriers)
    .orderBy(carriers.name);

  return NextResponse.json(allCarriers);
}
