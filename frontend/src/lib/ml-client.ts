class MLServiceClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = process.env.ML_SERVICE_URL || "http://ml-service:8000";
  }

  private async request(path: string, options?: RequestInit) {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: {
        "Content-Type": "application/json",
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
      body: JSON.stringify(data),
    });
  }

  async predictRoute(data: {
    carrierSlug: string;
    originRegion: string;
    destRegion: string;
  }) {
    return this.request("/predict/route", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async triggerScrape(trackingNumber: string, carrierSlug: string) {
    return this.request("/scrape/trigger", {
      method: "POST",
      body: JSON.stringify({ trackingNumber, carrierSlug }),
    });
  }

  async getModelStatus() {
    return this.request("/model/status");
  }

  async triggerRetrain() {
    return this.request("/train/trigger", { method: "POST" });
  }
}

export const mlClient = new MLServiceClient();
