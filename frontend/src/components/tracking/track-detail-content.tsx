"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { CyberCard, StatCard } from "@/components/ui/cyber-card";
import { TrackingTimeline, ConfidenceBar, StatusBadge } from "@/components/tracking/timeline";
import { useEventStream } from "@/hooks/use-event-stream";
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
import ShipmentRouteMap from "@/components/maps/shipment-map-dynamic";

interface ShipmentDetail {
  id: string;
  trackingNumber: string;
  carrier: { name: string; slug: string; trackingUrlTemplate: string | null };
  status: string;
  serviceType: string | null;
  originName: string | null;
  originLat: string | null;
  originLng: string | null;
  destName: string | null;
  destLat: string | null;
  destLng: string | null;
  shippedAt: string | null;
  deliveredAt: string | null;
  estimatedDelivery: string | null;
  events: {
    status: string;
    locationName: string | null;
    locationLat: string | null;
    locationLng: string | null;
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

  const loadData = useCallback(async () => {
    try {
      const res = await fetch(`/api/trackings/${shipmentId}`);
      if (res.ok) {
        setData(await res.json());
      }
    } catch {}
  }, [shipmentId]);

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

  useEventStream({
    onUpdate: (event) => {
      if (event.shipment_id === shipmentId) {
        loadData();
      }
    },
    enabled: !!data && data.status.toLowerCase() !== "delivered",
  });

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
    <div className="max-w-7xl mx-auto px-4 py-6 md:py-8 pb-24 md:pb-8">
      <div className="flex flex-col gap-3 mb-6 sm:flex-row sm:items-center sm:gap-4 sm:mb-8">
        <div className="flex w-full min-w-0 items-start gap-3 sm:flex-1">
          <Link
            href="/dashboard"
            className="mt-1 shrink-0 text-cyber-muted hover:text-cyber-cyan transition-colors"
            aria-label="Back to Dashboard"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="min-w-0 flex-1">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
              <h1 className="font-display text-base leading-snug text-cyber-text break-all sm:text-xl">
                {data.trackingNumber}
              </h1>
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={data.status} />
              </div>
            </div>
            <p className="text-sm text-cyber-muted font-mono break-words">
              {data.carrier.name}
              {data.serviceType ? ` - ${data.serviceType}` : ""}
            </p>
          </div>
        </div>
        {trackingUrl && (
          <a
            href={trackingUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="cyber-btn w-full text-xs sm:w-auto sm:shrink-0"
          >
            <ExternalLink className="w-3 h-3 mr-1" />
            Carrier Site
          </a>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
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
        <div className="lg:col-span-2 space-y-6">
          <CyberCard terminal title="Route Map" glow="cyan">
            <ShipmentRouteMap
              events={data.events.map((e) => ({
                ...e,
                locationLat: e.locationLat ? parseFloat(e.locationLat) : null,
                locationLng: e.locationLng ? parseFloat(e.locationLng) : null,
              }))}
              originLat={data.originLat ? parseFloat(data.originLat) : null}
              originLng={data.originLng ? parseFloat(data.originLng) : null}
              originName={data.originName}
              destLat={data.destLat ? parseFloat(data.destLat) : null}
              destLng={data.destLng ? parseFloat(data.destLng) : null}
              destName={data.destName}
              status={data.status}
            />
          </CyberCard>

          <CyberCard terminal title="Tracking Events">
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
            <CyberCard glow="cyan" terminal title="Delivery Prediction">
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-4 h-4 text-cyber-cyan" />
                <h3 className="text-sm font-display tracking-wide text-cyber-cyan">
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
        </div>
      </div>
    </div>
  );
}
