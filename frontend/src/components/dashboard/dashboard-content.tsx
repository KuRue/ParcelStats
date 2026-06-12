"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/tracking/timeline";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  Loader2,
  Package,
  Plus,
  Upload,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { useEventStream } from "@/hooks/use-event-stream";
import ParcelGlobe, { webglAvailable } from "@/components/globe/parcel-globe-dynamic";
import GlobalMap from "@/components/maps/global-map-dynamic";
import { formatRegionalDateHour, isDeliveredStatus, isIssueStatus } from "@/lib/utils";
import {
  detectCarrierSlug,
  isSpeedPakTrackingNumber,
  normalizeTrackingNumber,
} from "@/lib/carrier-detection";

interface Tracking {
  id: string;
  trackingNumber: string;
  carrier: { name: string; slug: string };
  status: string;
  estimatedDelivery: string | null;
  confidencePct: number | null;
  predictionSource: string | null;
  lastEvent: string | null;
  lastLocation: string | null;
  lastLat: string | null;
  lastLng: string | null;
  originName: string | null;
  originLat: string | null;
  originLng: string | null;
  destName: string | null;
  destLat: string | null;
  destLng: string | null;
  updatedAt: string;
  path: [number, number][];
}

interface BulkImportResult {
  status: string;
  received: number;
  valid: number;
  imported: number;
  queued: number;
  queueFailures: number;
  duplicates: number;
  invalid: { trackingNumber: string; reason: string }[];
  alreadyTracked: number;
  alreadyInSystem: number;
  maxImport: number;
}

function statusRank(status: string): number {
  if (isDeliveredStatus(status)) return 3;
  if (isIssueStatus(status)) return 2;
  return 1;
}

function updatedAtTime(tracking: Tracking): number {
  const time = new Date(tracking.updatedAt).getTime();
  return Number.isFinite(time) ? time : 0;
}

function parseBulkTrackingNumbers(value: string): string[] {
  return value
    .split(/[\s,;]+/)
    .map(normalizeTrackingNumber)
    .filter(Boolean);
}

function statusDotClass(status: string): string {
  if (isDeliveredStatus(status)) return "bg-cyber-green";
  if (isIssueStatus(status)) return "bg-cyber-red";
  return "bg-cyber-cyan";
}

function ParcelRow({
  tracking,
  selected,
  onSelect,
}: {
  tracking: Tracking;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => e.key === "Enter" && onSelect()}
      className={`group flex items-center gap-3 rounded border px-3 py-2.5 cursor-pointer transition-all ${
        selected
          ? "border-cyber-cyan/60 bg-cyber-cyan/10"
          : "border-cyber-border bg-cyber-card/60 hover:border-cyber-cyan/30"
      }`}
    >
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${statusDotClass(tracking.status)} ${
          !isDeliveredStatus(tracking.status) && !isIssueStatus(tracking.status)
            ? "animate-pulse"
            : ""
        }`}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-xs text-cyber-text">
          {tracking.trackingNumber}
        </p>
        <p className="truncate font-mono text-[10px] text-cyber-muted">
          {tracking.carrier.name}
          {tracking.lastLocation ? ` · ${tracking.lastLocation}` : ""}
        </p>
      </div>
      {tracking.estimatedDelivery && !isDeliveredStatus(tracking.status) && (
        <span className="shrink-0 font-mono text-[10px] text-cyber-cyan">
          {formatRegionalDateHour(tracking.estimatedDelivery)}
        </span>
      )}
      <Link
        href={`/track/${tracking.id}`}
        onClick={(e) => e.stopPropagation()}
        className="shrink-0 text-cyber-muted opacity-60 transition-colors hover:text-cyber-cyan group-hover:opacity-100"
        aria-label="Open details"
      >
        <ExternalLink className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

export function DashboardContent({ userId }: { userId: string }) {
  const [trackings, setTrackings] = useState<Tracking[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTracking, setNewTracking] = useState("");
  const [newCarrier, setNewCarrier] = useState("auto");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [bulkText, setBulkText] = useState("");
  const [bulkConfirmed, setBulkConfirmed] = useState(false);
  const [bulkImporting, setBulkImporting] = useState(false);
  const [bulkResult, setBulkResult] = useState<BulkImportResult | null>(null);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [carriers, setCarriers] = useState<{ name: string; slug: string }[]>([]);
  const [filter, setFilter] = useState("all");
  const [selectedShipment, setSelectedShipment] = useState<string | null>(null);
  const [hasWebgl, setHasWebgl] = useState(true);

  useEffect(() => {
    setHasWebgl(webglAvailable());
  }, []);

  const handleStatusChange = useCallback((shipmentId: string, newStatus: string) => {
    setTrackings((prev) =>
      prev.map((t) =>
        t.id === shipmentId ? { ...t, status: newStatus, updatedAt: new Date().toISOString() } : t
      )
    );
  }, []);

  const { connected: sseConnected, updateCount } = useEventStream({
    onUpdate: () => fetchTrackings(),
    onStatusChange: handleStatusChange,
  });

  useEffect(() => {
    fetchTrackings();
    fetchCarriers();
  }, []);

  async function fetchTrackings() {
    try {
      const res = await fetch("/api/trackings");
      if (res.ok) {
        const data = await res.json();
        setTrackings(data);
      }
    } finally {
      setLoading(false);
    }
  }

  async function fetchCarriers() {
    const res = await fetch("/api/trackings/carriers");
    if (res.ok) {
      setCarriers(await res.json());
    }
  }

  async function handleAddTracking(e: React.FormEvent) {
    e.preventDefault();
    const trackingNumber = normalizeTrackingNumber(newTracking);
    if (!trackingNumber) return;

    setAdding(true);
    setAddError(null);
    try {
      const res = await fetch("/api/trackings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trackingNumber,
          carrierSlug: newCarrier,
        }),
      });

      if (res.ok) {
        setNewTracking("");
        setNewCarrier("auto");
        fetchTrackings();
      } else {
        const data = await res.json().catch(() => null);
        setAddError(data?.error || "Failed to add tracking number");
      }
    } finally {
      setAdding(false);
    }
  }

  async function handleBulkImport(e: React.FormEvent) {
    e.preventDefault();
    const trackingNumbers = parseBulkTrackingNumbers(bulkText);
    if (trackingNumbers.length === 0) {
      setBulkError("Paste at least one SpeedPAK tracking number");
      return;
    }

    setBulkImporting(true);
    setBulkError(null);
    setBulkResult(null);
    try {
      const res = await fetch("/api/trackings/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trackingNumbers,
          confirmOwned: bulkConfirmed,
        }),
      });

      const data = await res.json().catch(() => null);
      if (res.ok) {
        setBulkResult(data);
        if (data.imported > 0) {
          setBulkText("");
          fetchTrackings();
        }
      } else {
        setBulkResult(data);
        setBulkError(data?.error || "Bulk import failed");
      }
    } finally {
      setBulkImporting(false);
    }
  }

  const detectedCarrierSlug = detectCarrierSlug(newTracking);
  const detectedCarrier = carriers.find((c) => c.slug === detectedCarrierSlug);
  const bulkNumbers = parseBulkTrackingNumbers(bulkText);
  const bulkUniqueNumbers = Array.from(new Set(bulkNumbers));
  const bulkSpeedPakCount = bulkUniqueNumbers.filter(isSpeedPakTrackingNumber).length;

  const filtered = (
    filter === "all"
      ? [...trackings]
      : trackings.filter((t) => {
          if (filter === "active") return !isDeliveredStatus(t.status) && !isIssueStatus(t.status);
          if (filter === "delivered") return isDeliveredStatus(t.status);
          if (filter === "issues") return isIssueStatus(t.status);
          return true;
        })
  ).sort((a, b) => {
    if (filter === "all") {
      const rankDiff = statusRank(a.status) - statusRank(b.status);
      if (rankDiff !== 0) return rankDiff;
    }
    return updatedAtTime(b) - updatedAtTime(a);
  });

  const stats = {
    total: trackings.length,
    active: trackings.filter(
      (t) => !isDeliveredStatus(t.status) && !isIssueStatus(t.status)
    ).length,
    delivered: trackings.filter((t) => isDeliveredStatus(t.status)).length,
    issues: trackings.filter((t) => isIssueStatus(t.status)).length,
  };

  const selected = trackings.find((t) => t.id === selectedShipment) ?? null;

  const globeShipments = trackings.map((t) => ({
    id: t.id,
    trackingNumber: t.trackingNumber,
    status: t.status,
    carrierName: t.carrier.name,
    originLat: t.originLat,
    originLng: t.originLng,
    destLat: t.destLat,
    destLng: t.destLng,
    lastLat: t.lastLat,
    lastLng: t.lastLng,
    path: t.path ?? [],
    originName: t.originName,
    destName: t.destName,
    lastLocation: t.lastLocation,
  }));

  return (
    <div className="lg:flex lg:h-[calc(100vh-4rem)]">
      {/* Globe pane */}
      <div className="relative h-[42vh] min-h-[280px] lg:h-auto lg:min-h-0 lg:flex-1">
        {hasWebgl ? (
          <ParcelGlobe
            shipments={globeShipments}
            selectedId={selectedShipment}
            onSelect={(id) =>
              setSelectedShipment(id === selectedShipment ? null : id)
            }
          />
        ) : (
          <div className="absolute inset-0">
            <GlobalMap
              shipments={trackings}
              onSelect={(id) =>
                setSelectedShipment(id === selectedShipment ? null : id)
              }
              selectedId={selectedShipment}
            />
          </div>
        )}

        {/* Live indicator */}
        <div className="pointer-events-none absolute right-3 top-3 flex items-center gap-1.5 rounded border border-cyber-border/60 bg-cyber-bg/70 px-2 py-1 backdrop-blur-sm">
          {sseConnected ? (
            <>
              <Wifi className="h-3 w-3 text-cyber-green" />
              <span className="font-mono text-[10px] text-cyber-green">LIVE</span>
              {updateCount > 0 && (
                <span className="font-mono text-[9px] text-cyber-muted">
                  {updateCount}
                </span>
              )}
            </>
          ) : (
            <>
              <WifiOff className="h-3 w-3 text-cyber-muted" />
              <span className="font-mono text-[10px] text-cyber-muted">OFFLINE</span>
            </>
          )}
        </div>

        {/* Legend */}
        <div className="pointer-events-none absolute left-3 top-3 hidden flex-col gap-1 rounded border border-cyber-border/60 bg-cyber-bg/70 px-2.5 py-2 backdrop-blur-sm md:flex">
          <span className="flex items-center gap-2 font-mono text-[10px] text-cyber-muted">
            <span className="h-0.5 w-4 bg-cyber-cyan" /> traveled
          </span>
          <span className="flex items-center gap-2 font-mono text-[10px] text-cyber-muted">
            <span className="h-0.5 w-4 border-t border-dashed border-cyber-purple" />{" "}
            predicted
          </span>
          <span className="flex items-center gap-2 font-mono text-[10px] text-cyber-muted">
            <span className="h-0.5 w-4 bg-cyber-green" /> delivered
          </span>
        </div>

        {/* Selected parcel card */}
        {selected && (
          <div className="absolute bottom-3 left-3 right-3 rounded border border-cyber-cyan/40 bg-cyber-bg/85 p-3 shadow-cyber-glow backdrop-blur-md md:right-auto md:w-[340px]">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="break-all font-mono text-sm text-cyber-cyan">
                  {selected.trackingNumber}
                </p>
                <p className="font-mono text-[11px] text-cyber-muted">
                  {selected.carrier.name}
                </p>
              </div>
              <button
                onClick={() => setSelectedShipment(null)}
                className="shrink-0 text-cyber-muted transition-colors hover:text-cyber-text"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={selected.status} />
              {selected.confidencePct != null && (
                <span className="font-mono text-[10px] text-cyber-muted">
                  {Math.round(selected.confidencePct)}% conf
                  {selected.predictionSource && (
                    <span className="ml-1 text-cyber-muted/50">
                      ({selected.predictionSource === "knowledge+lanes"
                        ? "calibrated"
                        : selected.predictionSource === "knowledge"
                          ? "baseline"
                          : "ML"})
                    </span>
                  )}
                </span>
              )}
            </div>
            {selected.lastEvent && (
              <p className="mt-2 line-clamp-2 text-[11px] text-cyber-muted">
                {selected.lastEvent}
              </p>
            )}
            <div className="mt-2 flex items-center justify-between gap-2">
              {selected.estimatedDelivery ? (
                <span className="font-mono text-[11px] text-cyber-text">
                  ETA {formatRegionalDateHour(selected.estimatedDelivery)}
                </span>
              ) : (
                <span />
              )}
              <Link
                href={`/track/${selected.id}`}
                className="cyber-btn px-2 py-1 text-[10px]"
              >
                Details
                <ExternalLink className="ml-1 inline h-3 w-3" />
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* Sidebar */}
      <aside className="border-cyber-border px-4 py-4 pb-24 lg:w-[400px] lg:shrink-0 lg:overflow-y-auto lg:border-l lg:pb-6">
        {/* Stats */}
        <div className="mb-4 grid grid-cols-4 gap-2">
          {[
            { label: "Total", value: stats.total, color: "text-cyber-text" },
            { label: "Active", value: stats.active, color: "text-cyber-cyan" },
            { label: "Done", value: stats.delivered, color: "text-cyber-green" },
            { label: "Issues", value: stats.issues, color: "text-cyber-red" },
          ].map((s) => (
            <button
              key={s.label}
              onClick={() =>
                setFilter(
                  s.label === "Total"
                    ? "all"
                    : s.label === "Done"
                    ? "delivered"
                    : s.label.toLowerCase()
                )
              }
              className="rounded border border-cyber-border bg-cyber-card/60 px-2 py-2 text-center transition-colors hover:border-cyber-cyan/30"
            >
              <p className={`font-display text-lg leading-none ${s.color}`}>
                {s.value}
              </p>
              <p className="mt-1 font-mono text-[9px] uppercase tracking-wider text-cyber-muted">
                {s.label}
              </p>
            </button>
          ))}
        </div>

        {/* Add tracking */}
        <form onSubmit={handleAddTracking} className="mb-3 space-y-2">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Enter tracking number..."
              value={newTracking}
              onChange={(e) => setNewTracking(e.target.value)}
              className="cyber-input min-w-0 flex-1 text-sm"
            />
            <button
              type="submit"
              disabled={adding || !newTracking || (newCarrier === "auto" && !detectedCarrierSlug)}
              className="cyber-btn-primary cyber-btn shrink-0 whitespace-nowrap"
            >
              {adding ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-1 h-4 w-4" />
              )}
              Track
            </button>
          </div>
          <select
            value={newCarrier}
            onChange={(e) => setNewCarrier(e.target.value)}
            className="cyber-input w-full text-sm"
          >
            <option value="auto">
              {detectedCarrier ? `Auto: ${detectedCarrier.name}` : "Auto-detect carrier"}
            </option>
            {carriers.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
          {addError && (
            <p className="font-mono text-xs text-cyber-red">{addError}</p>
          )}
        </form>

        {/* Bulk import (collapsed by default) */}
        <details className="group mb-4 rounded border border-cyber-border bg-cyber-card/40">
          <summary className="flex cursor-pointer items-center justify-between px-3 py-2 font-mono text-xs text-cyber-muted transition-colors hover:text-cyber-text [&::-webkit-details-marker]:hidden">
            <span className="flex items-center gap-2">
              <Upload className="h-3.5 w-3.5" />
              Bulk SpeedPAK Import
            </span>
            <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
          </summary>
          <form onSubmit={handleBulkImport} className="space-y-3 px-3 pb-3">
            <textarea
              value={bulkText}
              onChange={(e) => {
                setBulkText(e.target.value);
                setBulkResult(null);
                setBulkError(null);
              }}
              rows={4}
              placeholder="Paste SpeedPAK tracking numbers..."
              className="cyber-input w-full resize-y text-sm leading-6"
            />

            <label className="flex items-start gap-2 text-xs text-cyber-muted">
              <input
                type="checkbox"
                checked={bulkConfirmed}
                onChange={(e) => setBulkConfirmed(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-cyber-cyan"
              />
              <span>
                These are my tracking numbers, or I have permission to track them.
              </span>
            </label>

            <button
              type="submit"
              disabled={bulkImporting || !bulkConfirmed || bulkNumbers.length === 0}
              className="cyber-btn-primary cyber-btn w-full whitespace-nowrap disabled:opacity-50"
            >
              {bulkImporting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-1 h-4 w-4" />
              )}
              Import
            </button>

            {bulkNumbers.length > 0 && (
              <div className="flex flex-wrap gap-2 font-mono text-[11px] text-cyber-muted">
                <span>{bulkUniqueNumbers.length} unique</span>
                <span>{bulkSpeedPakCount} SpeedPAK</span>
                {bulkUniqueNumbers.length !== bulkNumbers.length && (
                  <span>{bulkNumbers.length - bulkUniqueNumbers.length} duplicate</span>
                )}
              </div>
            )}

            {bulkError && (
              <div className="flex items-start gap-2 text-xs text-cyber-red">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{bulkError}</span>
              </div>
            )}

            {bulkResult && !bulkError && (
              <div className="flex items-start gap-2 text-xs text-cyber-muted">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyber-green" />
                <span>
                  Imported {bulkResult.imported}, queued {bulkResult.queued}
                  {bulkResult.alreadyTracked > 0
                    ? `, ${bulkResult.alreadyTracked} already tracked`
                    : ""}
                  {bulkResult.alreadyInSystem > 0
                    ? `, ${bulkResult.alreadyInSystem} already in system`
                    : ""}
                  {bulkResult.invalid.length > 0
                    ? `, ${bulkResult.invalid.length} rejected`
                    : ""}
                  {bulkResult.queueFailures > 0
                    ? `, ${bulkResult.queueFailures} queue failures`
                    : ""}
                </span>
              </div>
            )}

            {(bulkResult?.invalid.length ?? 0) > 0 && (
              <div className="rounded border border-cyber-border/60 bg-cyber-bg/40 p-2 font-mono text-[11px] text-cyber-muted">
                {bulkResult?.invalid.slice(0, 5).map((item) => (
                  <div key={item.trackingNumber} className="break-all">
                    {item.trackingNumber}: {item.reason}
                  </div>
                ))}
                {(bulkResult?.invalid.length ?? 0) > 5 && (
                  <div>{(bulkResult?.invalid.length ?? 0) - 5} more rejected</div>
                )}
              </div>
            )}
          </form>
        </details>

        {/* Filters */}
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {["all", "active", "delivered", "issues"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded border px-2.5 py-1 font-mono text-[11px] transition-all ${
                filter === f
                  ? "border-cyber-cyan/50 bg-cyber-cyan/10 text-cyber-cyan"
                  : "border-cyber-border text-cyber-muted hover:text-cyber-text"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
          <span className="ml-auto font-mono text-[11px] text-cyber-muted">
            {filtered.length}
          </span>
        </div>

        {/* Parcel list */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-cyber-cyan" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded border border-cyber-border bg-cyber-card/40 py-10 text-center">
            <Package className="mx-auto mb-3 h-10 w-10 text-cyber-muted/30" />
            <p className="px-4 font-mono text-xs text-cyber-muted">
              {trackings.length === 0
                ? "No shipments tracked yet. Add one above to see it on the globe."
                : "No shipments match this filter."}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((t) => (
              <ParcelRow
                key={t.id}
                tracking={t}
                selected={t.id === selectedShipment}
                onSelect={() =>
                  setSelectedShipment(t.id === selectedShipment ? null : t.id)
                }
              />
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
