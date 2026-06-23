"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { CyberCard } from "@/components/ui/cyber-card";
import { TrackingTimeline, ConfidenceBar, StatusBadge } from "@/components/tracking/timeline";
import { useEventStream } from "@/hooks/use-event-stream";
import { formatDistanceToNowStrict, differenceInCalendarDays } from "date-fns";
import {
  Package,
  Brain,
  ArrowLeft,
  ExternalLink,
  Loader2,
  Trash2,
  Copy,
  Check,
  MapPin,
  Truck,
} from "lucide-react";
import Link from "next/link";
import ShipmentRouteMap from "@/components/maps/shipment-map-dynamic";
import {
  formatRegionalDateHour,
  isDeliveredStatus,
  isIssueStatus,
} from "@/lib/utils";
import { triggerUPSFetch } from "@/lib/ups-client-fetch";

interface FlightPosition {
  icao24: string;
  callsign: string;
  latitude: number;
  longitude: number;
  altitude: number | null;
  velocity: number | null;
  heading: number | null;
  on_ground: boolean;
  origin_country: string;
  distance_to_origin_km?: number;
  distance_to_dest_km?: number;
}

interface ShipmentDetail {
  canDelete?: boolean;
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
    predictionSource: string | null;
    calibrationSamples: number | null;
  } | null;
}

interface FutureStop {
  stopOrder: number;
  locationName: string;
  locationLat: number | null;
  locationLng: number | null;
  status: string;
  frequencyPct: number;
  eta: string;
  medianDaysFromStart: number;
  p10Days: number;
  p90Days: number;
}

interface RoutePrediction {
  status: string;
  route?: {
    carrierSlug: string;
    originCountry: string;
    destCountry: string;
    label: string;
    matchedStops: number;
    totalPatternStops: number;
    totalEvents: number;
    score: number;
    sampleCount: number;
    futureStops: FutureStop[];
  };
}

function placeName(location: string | null): string {
  if (!location) return "Unknown";
  return location.split(",")[0].trim() || "Unknown";
}

function relative(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return formatDistanceToNowStrict(date, { addSuffix: true });
}

function eventTimeLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatRegionalDateHour(date);
}

export function TrackDetailContent({
  shipmentId,
  authenticated,
}: {
  shipmentId: string;
  authenticated: boolean;
}) {
  const router = useRouter();
  const [data, setData] = useState<ShipmentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [pendingPrediction, setPendingPrediction] = useState(false);
  const fetchedPredictionRef = useRef(false);
  const [routePrediction, setRoutePrediction] = useState<RoutePrediction | null>(null);
  const upsFetchRef = useRef(false);
  const [flights, setFlights] = useState<FlightPosition[]>([]);

  const handleDelete = useCallback(async () => {
    if (!window.confirm("Stop tracking this shipment? This cannot be undone.")) {
      return;
    }
    setDeleting(true);
    try {
      const res = await fetch(`/api/trackings/${shipmentId}`, { method: "DELETE" });
      if (res.ok) {
        router.push("/dashboard");
        return;
      }
    } catch {}
    setDeleting(false);
  }, [shipmentId, router]);

  const handleCopy = useCallback(async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.trackingNumber);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  }, [data]);

  const loadData = useCallback(async () => {
    try {
      const res = await fetch(`/api/trackings/${shipmentId}`);
      if (res.ok) {
        setData(await res.json());
      }
    } catch {}
  }, [shipmentId]);
  const loadedStatus = data?.status ?? "";
  const loadedShippedAt = data?.shippedAt ?? null;

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

  // On-demand prediction: request one if missing OR stale (predicted date in past)
  useEffect(() => {
    if (!data || isDeliveredStatus(data.status)) return;

    const isStale = data.prediction
      ? new Date(data.prediction.predictedDelivery).getTime() < Date.now()
      : true;
    if (!isStale) return;
    if (fetchedPredictionRef.current) return;

    const region = (name: string | null) =>
      name ? name.split(",").slice(-1)[0].trim() : undefined;

    setPendingPrediction(true);
    fetchedPredictionRef.current = true;

    fetch("/api/predictions/eta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        trackingNumber: data.trackingNumber,
        carrierSlug: data.carrier.slug,
        originRegion: region(data.originName),
        destRegion: region(data.destName),
        serviceType: data.serviceType ?? undefined,
      }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((result) => {
        if (result?.status === "ok" && result.prediction) {
          setData((prev) =>
            prev ? { ...prev, prediction: result.prediction } : prev
          );
        }
      })
      .catch(() => {})
      .finally(() => setPendingPrediction(false));
  }, [data]);

  // Fetch route prediction (future stops) after initial load
  useEffect(() => {
    if (!loadedStatus || !loadedShippedAt) return;
    if (isDeliveredStatus(loadedStatus) || isIssueStatus(loadedStatus)) return;

    fetch(`/api/predictions/shipment-route/${shipmentId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((result) => {
        if (result?.status === "ok" && result.route) {
          setRoutePrediction(result);
        }
      })
      .catch(() => {})
  }, [shipmentId, loadedShippedAt, loadedStatus]);

  // Client-side UPS fetch: if server scraping returned client_fetch_required
  useEffect(() => {
    if (!data || upsFetchRef.current) return;
    if (data.carrier.slug !== "ups" || data.status !== "client_fetch_required") return;

    upsFetchRef.current = true;

    triggerUPSFetch(data.trackingNumber, data.id).then((result) => {
      if (result && result.events > 0) {
        loadData();
      }
    });
  }, [data, loadData]);

  const isUPSClientFetch =
    data?.carrier?.slug === "ups" && data?.status === "client_fetch_required";

  const isInternationalTransit = (() => {
    if (!data || !data.originLat || !data.destLat) return false;
    const oLng = parseFloat(data.originLng || "");
    const dLng = parseFloat(data.destLng || "");
    if (isNaN(oLng) || isNaN(dLng)) return false;
    const originCountry = data.originName?.split(",").slice(-1)[0].trim();
    const destCountry = data.destName?.split(",").slice(-1)[0].trim();
    return originCountry !== destCountry;
  })();

  useEffect(() => {
    if (!data || !isInternationalTransit || isDeliveredStatus(data.status)) return;

    const oLat = parseFloat(data.originLat || "");
    const oLng = parseFloat(data.originLng || "");
    const dLat = parseFloat(data.destLat || "");
    const dLng = parseFloat(data.destLng || "");
    if (isNaN(oLat) || isNaN(oLng) || isNaN(dLat) || isNaN(dLng)) return;

    let active = true;
    const loadFlights = () => {
      fetch(`/api/flights?origin_lat=${oLat}&origin_lng=${oLng}&dest_lat=${dLat}&dest_lng=${dLng}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((result) => {
          if (active && result?.flights) {
            setFlights(result.flights);
          }
        })
        .catch(() => {});
    };

    loadFlights();
    const id = window.setInterval(loadFlights, 60000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [data, isInternationalTransit]);

  useEventStream({
    onUpdate: (event) => {
      if (event.shipment_id === shipmentId) {
        fetchedPredictionRef.current = false;
        loadData();
      }
    },
    enabled: !!data && !isDeliveredStatus(data.status),
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

  const delivered = isDeliveredStatus(data.status);
  const issue = isIssueStatus(data.status);
  const eta = data.prediction?.predictedDelivery ?? data.estimatedDelivery;
  const etaDate = eta ? new Date(eta) : null;
  const shippedDate = data.shippedAt ? new Date(data.shippedAt) : null;
  const deliveredDate = data.deliveredAt ? new Date(data.deliveredAt) : null;
  const lastEvent = data.events[0] ?? null;

  const transitDays = shippedDate
    ? differenceInCalendarDays(deliveredDate ?? new Date(), shippedDate)
    : null;

  // Time-based journey progress between ship date and (actual or predicted) arrival
  let progress: number | null = null;
  if (delivered) {
    progress = 1;
  } else if (shippedDate && etaDate && etaDate > shippedDate) {
    const ratio =
      (Date.now() - shippedDate.getTime()) / (etaDate.getTime() - shippedDate.getTime());
    progress = Math.min(0.96, Math.max(0.04, ratio));
  }

  const futureStops = routePrediction?.route?.futureStops ?? [];
  const timelineEvents = [
    ...data.events.map((e, i) => ({
      status: e.status,
      location: e.locationName || undefined,
      description: e.description || undefined,
      time: eventTimeLabel(e.eventTime),
      sortTime: new Date(e.eventTime).getTime(),
      isLatest: i === 0,
      predicted: false,
    })),
    ...futureStops.map((stop) => {
      const etaDate = new Date(stop.eta);
      const common =
        stop.frequencyPct < 100
          ? `${Math.round(stop.frequencyPct)}% common`
          : "Expected destination";
      const sampleText = routePrediction?.route?.sampleCount
        ? `${routePrediction.route.sampleCount} route samples`
        : "Route forecast";

      return {
        status: stop.status,
        location: stop.locationName,
        description: `${common} · ${sampleText}`,
        time: !Number.isNaN(etaDate.getTime())
          ? formatRegionalDateHour(etaDate)
          : "Timing unknown",
        sortTime: etaDate.getTime(),
        isLatest: false,
        predicted: true,
      };
    }),
  ]
    .sort((a, b) => {
      const aTime = Number.isNaN(a.sortTime) ? -Infinity : a.sortTime;
      const bTime = Number.isNaN(b.sortTime) ? -Infinity : b.sortTime;
      if (aTime !== bTime) return bTime - aTime;
      return Number(a.predicted ?? false) - Number(b.predicted ?? false);
    })
    .map(({ sortTime, ...event }) => event);
  const timelineTitle =
    futureStops.length > 0
      ? `Tracking Events (${data.events.length} + ${futureStops.length} forecast)`
      : `Tracking Events (${data.events.length})`;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 md:py-8 pb-24 md:pb-8">
      {/* Header */}
      <div className="flex flex-col gap-3 mb-6 sm:flex-row sm:items-center sm:gap-4">
        <div className="flex w-full min-w-0 items-start gap-3 sm:flex-1">
          <Link
            href="/dashboard"
            className="mt-1 shrink-0 text-cyber-muted hover:text-cyber-cyan transition-colors"
            aria-label="Back to Dashboard"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-base leading-snug text-cyber-text break-all sm:text-xl">
                {data.trackingNumber}
              </h1>
              <button
                onClick={handleCopy}
                className="shrink-0 text-cyber-muted hover:text-cyber-cyan transition-colors"
                aria-label="Copy tracking number"
                title="Copy tracking number"
              >
                {copied ? (
                  <Check className="w-4 h-4 text-cyber-green" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
              <StatusBadge status={data.status} />
            </div>
            <p className="text-sm text-cyber-muted font-mono break-words mt-0.5">
              {data.carrier.name}
              {data.serviceType ? ` · ${data.serviceType}` : ""}
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:shrink-0">
          {trackingUrl && (
            <a
              href={trackingUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="cyber-btn w-full text-xs sm:w-auto"
            >
              <ExternalLink className="w-3 h-3 mr-1" />
              Carrier Site
            </a>
          )}
          {data.canDelete && (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="cyber-btn w-full text-xs sm:w-auto text-cyber-red border-cyber-red/40 hover:border-cyber-red disabled:opacity-50"
            >
              <Trash2 className="w-3 h-3 mr-1 inline" />
              {deleting ? "Removing..." : "Stop Tracking"}
            </button>
          )}
        </div>
      </div>

      {/* UPS embedded tracking */}
      {isUPSClientFetch && (
        <CyberCard glow="purple" className="mb-6">
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-display text-sm font-bold text-cyber-purple mb-1">
                  UPS Live Tracking
                </p>
                <p className="font-mono text-xs text-cyber-muted">
                  Embedded from UPS.com — your tracking data loads directly in your browser.
                </p>
              </div>
              <a
                href={`https://www.ups.com/track?trackNums=${encodeURIComponent(data.trackingNumber)}&loc=en_US`}
                target="_blank"
                rel="noopener noreferrer"
                className="cyber-btn text-xs shrink-0"
              >
                <ExternalLink className="w-3 h-3 mr-1" />
                Open on UPS.com
              </a>
            </div>
            <div className="rounded border border-cyber-border overflow-hidden bg-white" style={{ height: 500 }}>
              <iframe
                src={`https://www.ups.com/track?trackNums=${encodeURIComponent(data.trackingNumber)}&loc=en_US`}
                className="w-full h-full border-0"
                title="UPS Tracking"
                loading="lazy"
                sandbox="allow-scripts allow-same-origin allow-popups"
              />
            </div>
          </div>
        </CyberCard>
      )}

      {/* ETA hero + journey progress */}
      <CyberCard
        glow={delivered ? "green" : issue ? "none" : "cyan"}
        className="mb-6"
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            {delivered ? (
              <>
                <p className="stat-label mb-1">Delivered</p>
                <p className="font-display text-2xl font-bold text-cyber-green text-shadow-cyber">
                  {deliveredDate ? formatRegionalDateHour(deliveredDate) : "Confirmed"}
                </p>
                {transitDays != null && (
                  <p className="mt-1 font-mono text-xs text-cyber-muted">
                    {transitDays} day{transitDays === 1 ? "" : "s"} in transit
                  </p>
                )}
              </>
            ) : issue ? (
              <>
                <p className="stat-label mb-1">Attention needed</p>
                <p className="font-display text-xl font-bold text-cyber-red">
                  {lastEvent?.description || "Tracking issue"}
                </p>
              </>
            ) : etaDate ? (
              <>
                <p className="stat-label mb-1">Estimated arrival</p>
                <p className="font-display text-2xl font-bold text-cyber-cyan text-shadow-cyber">
                  {relative(etaDate)}
                </p>
                <p className="mt-1 font-mono text-xs text-cyber-muted">
                  {formatRegionalDateHour(etaDate)}
                  {data.prediction?.confidenceLow && data.prediction?.confidenceHigh
                    ? ` · window ${formatRegionalDateHour(
                        data.prediction.confidenceLow
                      )} – ${formatRegionalDateHour(data.prediction.confidenceHigh)}`
                    : ""}
                </p>
              </>
            ) : (
              <>
                <p className="stat-label mb-1">Estimated arrival</p>
                <p className="font-display text-xl font-bold text-cyber-muted">
                  Awaiting first scan
                </p>
              </>
            )}
          </div>
        </div>

        {/* Journey rail */}
        <div className="mt-5">
          <div className="flex items-center justify-between gap-3 font-mono text-[11px] text-cyber-muted">
            <span className="flex min-w-0 items-center gap-1">
              <MapPin className="h-3 w-3 shrink-0 text-cyber-purple" />
              <span className="truncate">{placeName(data.originName)}</span>
            </span>
            {lastEvent?.locationName && !delivered && (
              <span className="hidden min-w-0 items-center gap-1 sm:flex">
                <Truck className="h-3 w-3 shrink-0 text-cyber-cyan" />
                <span className="truncate text-cyber-text">
                  {placeName(lastEvent.locationName)}
                </span>
              </span>
            )}
            <span className="flex min-w-0 items-center gap-1">
              <span className="truncate">{placeName(data.destName)}</span>
              <MapPin className="h-3 w-3 shrink-0 text-cyber-cyan" />
            </span>
          </div>
          <div className="relative mt-2 h-1.5 rounded-full bg-cyber-border/40">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                delivered
                  ? "bg-cyber-green"
                  : issue
                  ? "bg-cyber-red/70"
                  : "bg-gradient-to-r from-cyber-purple to-cyber-cyan"
              }`}
              style={{ width: `${(progress ?? 0.04) * 100}%` }}
            />
            {!delivered && progress != null && (
              <span
                className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full bg-cyber-cyan shadow-cyber-glow animate-pulse"
                style={{ left: `calc(${progress * 100}% - 6px)` }}
              />
            )}
          </div>
        </div>
      </CyberCard>

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
              futureStops={futureStops}
              flights={isInternationalTransit ? flights : []}
            />
          </CyberCard>

          <CyberCard terminal title={timelineTitle}>
            {timelineEvents.length === 0 ? (
              <p className="py-6 text-center font-mono text-xs text-cyber-muted">
                No scans yet — events appear here once the carrier registers the
                package.
              </p>
            ) : (
              <TrackingTimeline events={timelineEvents} />
            )}
          </CyberCard>
        </div>

        <div className="space-y-6">
          {data.prediction && !delivered && (
            <CyberCard glow="cyan" terminal title="AI Prediction">
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-4 h-4 text-cyber-cyan" />
                <h3 className="text-sm font-display tracking-wide text-cyber-cyan">
                  Delivery Forecast
                </h3>
              </div>

              <div className="space-y-4">
                <div>
                  <p className="stat-label mb-1">Predicted Delivery</p>
                  <p className="text-lg font-display font-bold text-cyber-cyan text-shadow-cyber">
                    {formatRegionalDateHour(data.prediction.predictedDelivery)}
                  </p>
                </div>

                {data.prediction.confidenceLow && data.prediction.confidenceHigh && (
                  <div>
                    <p className="stat-label mb-1">Confidence Window</p>
                    <p className="text-sm font-mono text-cyber-text">
                      {formatRegionalDateHour(data.prediction.confidenceLow)} –{" "}
                      {formatRegionalDateHour(data.prediction.confidenceHigh)}
                    </p>
                  </div>
                )}

                <ConfidenceBar
                  value={Math.round(data.prediction.confidencePct)}
                  label="Confidence"
                />

                <p className="text-[10px] text-cyber-muted/60 font-mono">
                  Model {data.prediction.modelVersion}
                  {data.prediction.predictionSource && (
                    <span className="ml-2 px-1.5 py-0.5 rounded text-[9px] border border-cyber-cyan/30 text-cyber-cyan/80">
                      {data.prediction.predictionSource === "knowledge+lanes"
                        ? "Calibrated"
                        : data.prediction.predictionSource === "knowledge"
                          ? "Baseline"
                          : "ML"}
                    </span>
                  )}
                </p>
              </div>
            </CyberCard>
          )}

          {isInternationalTransit && flights.length > 0 && (
            <CyberCard glow="purple" terminal title="Live Cargo Flights">
              <div className="space-y-2">
                {flights.slice(0, 5).map((f) => {
                  const altKm = f.altitude ? (f.altitude / 1000).toFixed(1) : "?";
                  const speedKmh = f.velocity ? Math.round(f.velocity * 3.6) : "?";
                  return (
                    <div
                      key={f.icao24}
                      className="flex items-center justify-between border-b border-cyber-border/30 pb-2 last:border-0 last:pb-0"
                    >
                      <div>
                        <p className="font-mono text-sm text-cyber-yellow font-bold">
                          {f.callsign}
                        </p>
                        <p className="font-mono text-[10px] text-cyber-muted">
                          {f.on_ground ? "On ground" : `${altKm} km · ${speedKmh} km/h`}
                          {f.origin_country ? ` · ${f.origin_country}` : ""}
                        </p>
                      </div>
                      {f.distance_to_dest_km != null && (
                        <p className="font-mono text-[10px] text-cyber-cyan shrink-0">
                          {f.distance_to_dest_km} km to dest
                        </p>
                      )}
                    </div>
                  );
                })}
                <p className="font-mono text-[10px] text-cyber-muted pt-1">
                  Data from OpenSky Network · updates every 60s
                </p>
              </div>
            </CyberCard>
          )}

          <CyberCard terminal title="Shipment Data">
            <dl className="space-y-2.5">
              {[
                { label: "Carrier", value: data.carrier.name },
                { label: "Service", value: data.serviceType },
                { label: "Origin", value: data.originName },
                { label: "Destination", value: data.destName },
                {
                  label: "Shipped",
                  value: shippedDate
                    ? `${formatRegionalDateHour(shippedDate)} · ${relative(shippedDate)}`
                    : null,
                },
                {
                  label: delivered ? "Total transit" : "In transit",
                  value:
                    transitDays != null
                      ? `${transitDays} day${transitDays === 1 ? "" : "s"}`
                      : null,
                },
                { label: "Scans", value: String(data.events.length) },
                {
                  label: "Last update",
                  value: lastEvent ? relative(lastEvent.eventTime) : null,
                },
              ]
                .filter((row) => row.value)
                .map((row) => (
                  <div
                    key={row.label}
                    className="flex items-start justify-between gap-3 border-b border-cyber-border/30 pb-2 last:border-0 last:pb-0"
                  >
                    <dt className="shrink-0 font-mono text-[11px] uppercase tracking-wider text-cyber-muted">
                      {row.label}
                    </dt>
                    <dd className="min-w-0 break-words text-right font-mono text-xs text-cyber-text">
                      {row.value}
                    </dd>
                  </div>
                ))}
            </dl>
          </CyberCard>
        </div>
      </div>
    </div>
  );
}
