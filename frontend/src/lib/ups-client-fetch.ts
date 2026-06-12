export async function triggerUPSFetch(
  trackingNumber: string,
  shipmentId: string
): Promise<{ status: string; events: number } | null> {
  try {
    const resp = await fetch("/api/trackings/ups-client-fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trackingNumber, shipmentId }),
    });

    if (!resp.ok) return null;

    return resp.json();
  } catch {
    return null;
  }
}
