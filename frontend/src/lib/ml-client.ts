export function internalApiKeyHeader(): Record<string, string> {
  const key = process.env.INTERNAL_API_KEY;
  return key ? { "X-Internal-API-Key": key } : {};
}

class MLServiceClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = process.env.ML_SERVICE_URL || "http://ml-service:8000";
  }

  private async request(path: string, options?: RequestInit) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...internalApiKeyHeader(),
        ...options?.headers,
      },
      ...options,
    });

    if (!res.ok) {
      const error = await res.text();
      throw new Error(`ML service error: ${res.status} - ${error}`);
    }

    return res.json();
  }

  async predictEta(data: {
    trackingNumber: string;
    carrierSlug: string;
    originRegion?: string;
    destRegion?: string;
    serviceType?: string;
  }) {
    return this.request("/predict/eta", {
      method: "POST",
      body: JSON.stringify({
        tracking_number: data.trackingNumber,
        carrier_slug: data.carrierSlug,
        origin_region: data.originRegion,
        dest_region: data.destRegion,
        service_type: data.serviceType,
      }),
    });
  }

  async predictRoute(data: {
    carrierSlug: string;
    originRegion: string;
    destRegion: string;
  }) {
    return this.request("/predict/route", {
      method: "POST",
      body: JSON.stringify({
        carrier_slug: data.carrierSlug,
        origin_region: data.originRegion,
        dest_region: data.destRegion,
      }),
    });
  }

  async triggerScrape(trackingNumber: string, carrierSlug: string, shipmentId?: string) {
    return this.request("/scrape/trigger", {
      method: "POST",
      body: JSON.stringify({
        tracking_number: trackingNumber,
        carrier_slug: carrierSlug,
        shipment_id: shipmentId,
      }),
    });
  }

  async getAccuracy() {
    return this.request("/predict/accuracy");
  }

  async getModelStatus() {
    return this.request("/train/status");
  }

  async getHealth() {
    return this.request("/health");
  }

  async triggerRetrain() {
    return this.request("/train/trigger", { method: "POST" });
  }
}

export const mlClient = new MLServiceClient();
