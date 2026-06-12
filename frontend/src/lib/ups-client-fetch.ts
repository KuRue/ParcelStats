interface UPSTrackEvent {
  date: string;
  time: string;
  gmtDate?: string;
  gmtTime?: string;
  location?: {
    address?: {
      city?: string;
      stateProvince?: string;
      postalCode?: string;
      countryCode?: string;
      country?: string;
    };
  };
  status?: {
    description?: string;
    simplifiedTextDescription?: string;
    type?: string;
    code?: string;
  };
}

interface UPSAPIResponse {
  trackResponse?: {
    shipment?: Array<{
      package?: Array<{
        currentStatus?: {
          description?: string;
          simplifiedTextDescription?: string;
        };
        statusDescription?: string;
        service?: { description?: string };
        activity?: UPSTrackEvent[];
        deliveryDate?: Array<{ type: string; date: string }>;
        deliveryTime?: Array<{
          type: string;
          startTime?: string;
          endTime?: string;
        }>;
      }>;
    }>;
  };
}

export async function fetchUPSTracking(trackingNumber: string): Promise<UPSAPIResponse | null> {
  try {
    const resp = await fetch(
      `https://webapis.ups.com/track/api/Track/GetStatus`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          Locale: "en_US",
          Requester: "ST/track.web",
          TrackingNumber: [trackingNumber],
        }),
      }
    );

    if (!resp.ok) {
      console.warn(`UPS client fetch failed: HTTP ${resp.status}`);
      return null;
    }

    const data: UPSAPIResponse = await resp.json();
    return data;
  } catch (error) {
    console.warn("UPS client fetch error:", error);
    return null;
  }
}

export async function fetchUPSTrackingViaPage(
  trackingNumber: string
): Promise<UPSAPIResponse | null> {
  try {
    const resp = await fetch(
      `https://www.ups.com/track?trackNums=${encodeURIComponent(trackingNumber)}&loc=en_US`,
      {
        credentials: "omit",
        headers: {
          Accept: "text/html",
        },
      }
    );

    if (!resp.ok) {
      console.warn(`UPS page fetch failed: HTTP ${resp.status}`);
      return null;
    }

    const html = await resp.text();

    const jsonMatch = html.match(
      /window\s*\.\s*UPS\s*\.\s*trackingData\s*=\s*({[\s\S]*?});/
    );
    if (jsonMatch) {
      return JSON.parse(jsonMatch[1]) as UPSAPIResponse;
    }

    return null;
  } catch (error) {
    console.warn("UPS page fetch error:", error);
    return null;
  }
}

export async function submitUPSClientFetch(
  trackingNumber: string,
  shipmentId: string,
  rawData: UPSAPIResponse
): Promise<{ status: string; events: number } | null> {
  try {
    const resp = await fetch("/api/trackings/ups-client-fetch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        trackingNumber,
        shipmentId,
        rawData,
      }),
    });

    if (!resp.ok) {
      console.warn(`UPS client fetch submit failed: HTTP ${resp.status}`);
      return null;
    }

    return resp.json();
  } catch (error) {
    console.warn("UPS client fetch submit error:", error);
    return null;
  }
}
