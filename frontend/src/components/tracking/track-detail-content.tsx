"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { CyberCard, StatCard } from "@/components/ui/cyber-card";
import { TrackingTimeline, ConfidenceBar, StatusBadge } from "@/components/tracking/timeline";
import {
  Package,
  Clock,
  MapPin,
  Brain,
  ArrowLeft,
  ExternalLink,
  Loader2,
  Activity,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";

interface ShipmentDetail {
  id: string;
  trackingNumber: string;
  carrier: { name: string; slug: string; trackingUrlTemplate: string | null };
  status: string;
  serviceType: string | null;
  originName: string | null;
  destName: string | null;
  shippedAt: string | null;
  deliveredAt: string | null;
  estimatedDelivery: string | null;
  events: {
    status: string;
    locationName: string | null;
    description: string | null;
    eventTime: string;
  }[];
  prediction: {
    predictedDelivery: string;
    confidenceLow: string | null;
    confidenceHigh: string | null;
    confidencePct: number;
    modelVersion: string;
  } | null;
}

export function TrackDetailContent({
  shipmentId,
  authenticated,
}: {
  shipmentId: string;
  authenticated: boolean;
}) {
  const [data, setData] = useState<ShipmentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/api/trackings/${shipmentId}`);
        if (res.ok) {
          setData(await res.json());
        } else {
          setError("Shipment not found");
        }
      } catch {
        setError("Failed to load shipment data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [shipmentId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-cyber-cyan animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <Package className="w-12 h-12 text-cyber-red/50 mx-auto mb-4" />
        <p className="text-cyber-red font-mono">{error || "Not found"}</p>
        <Link href="/dashboard" className="cyber-btn mt-4 inline-block">
          <ArrowLeft className="w-4 h-4 mr-2 inline" />
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const trackingUrl = data.carrier.trackingUrlTemplate
    ? data.carrier.trackingUrlTemplate.replace("{tracking_number}", data.trackingNumber)
    : null;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center gap-4 mb-8">
        <Link
          href="/dashboard"
          className="text-cyber-muted hover:text-cyber-cyan transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="font-display text-xl text-cyber-text">
              {data.trackingNumber}
            </h1>
            <StatusBadge status={data.status} />
          </div>
          <p className="text-sm text-cyber-muted font-mono">
            {data.carrier.name}
            {data.serviceType ? ` - ${data.serviceType}` : ""}
          </p>
        </div>
        {trackingUrl && (
          <a
            href={trackingUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="cyber-btn text-xs"
          >
            <ExternalLink className="w-3 h-3 mr-1" />
            Carrier Site
          </a>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {data.originName && (
          <StatCard label="Origin" value={data.originName} color="purple" />
        )}
        {data.destName && (
          <StatCard label="Destination" value={data.destName} color="cyan" />
        )}
        {data.shippedAt && (
          <StatCard
            label="Shipped"
            value={new Date(data.shippedAt).toLocaleDateString()}
            color="yellow"
          />
        )}
        {data.deliveredAt && (
          <StatCard
            label="Delivered"
            value={new Date(data.deliveredAt).toLocaleDateString()}
            color="green"
          />
        )}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <CyberCard terminal title="shipment://events">
            <h2 className="text-sm font-display uppercase tracking-wider text-cyber-cyan mb-4">
              Tracking Events
            </h2>
            <TrackingTimeline
              events={data.events.map((e, i) => ({
                status: e.status,
                location: e.locationName || undefined,
                description: e.description || undefined,
                time: new Date(e.eventTime).toLocaleString(),
                isLatest: i === 0,
              }))}
            />
          </CyberCard>
        </div>

        <div className="space-y-4">
          {data.prediction && (
            <CyberCard glow="cyan" terminal title="ml://prediction">
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-4 h-4 text-cyber-cyan" />
                <h3 className="text-sm font-display uppercase tracking-wider text-cyber-cyan">
                  AI Prediction
                </h3>
              </div>

              <div className="space-y-4">
                <div>
                  <p className="stat-label mb-1">Predicted Delivery</p>
                  <p className="text-lg font-display font-bold text-cyber-cyan text-shadow-cyber">
                    {new Date(
                      data.prediction.predictedDelivery
                    ).toLocaleDateString()}
                  </p>
                </div>

                {data.prediction.confidenceLow &&
                  data.prediction.confidenceHigh && (
                    <div>
                      <p className="stat-label mb-1">Confidence Window</p>
                      <p className="text-sm font-mono text-cyber-text">
                        {new Date(
                          data.prediction.confidenceLow
                        ).toLocaleDateString()}{" "}
                        -{" "}
                        {new Date(
                          data.prediction.confidenceHigh
                        ).toLocaleDateString()}
                      </p>
                    </div>
                  )}

                <ConfidenceBar
                  value={data.prediction.confidencePct}
                  label="Confidence"
                />

                <p className="text-[10px] text-cyber-muted/60 font-mono">
                  Model v{data.prediction.modelVersion}
                </p>
              </div>
            </CyberCard>
          )}

          <CyberCard terminal title="map://route">
            <div className="aspect-square bg-cyber-surface rounded border border-cyber-border flex items-center justify-center">
              <div className="text-center">
                <MapPin className="w-8 h-8 text-cyber-cyan/30 mx-auto mb-2" />
                <p className="text-xs text-cyber-muted font-mono">
                  Route map loading...
                </p>
              </div>
            </div>
          </CyberCard>
        </div>
      </div>
    </div>
  );
}
