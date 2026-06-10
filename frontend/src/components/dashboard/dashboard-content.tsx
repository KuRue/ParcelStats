"use client";

import { useState, useEffect, useCallback } from "react";
import { CyberCard, StatCard } from "@/components/ui/cyber-card";
import { TrackingCard } from "@/components/tracking/tracking-card";
import { Navbar } from "@/components/ui/navbar";
import { Plus, Search, Activity, Package, Brain, Loader2, Wifi, WifiOff } from "lucide-react";
import { useEventStream } from "@/hooks/use-event-stream";

interface Tracking {
  id: string;
  trackingNumber: string;
  carrier: { name: string; slug: string };
  status: string;
  estimatedDelivery: string | null;
  confidencePct: number | null;
  lastEvent: string | null;
  lastLocation: string | null;
  updatedAt: string;
}

export function DashboardContent({ userId }: { userId: string }) {
  const [trackings, setTrackings] = useState<Tracking[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTracking, setNewTracking] = useState("");
  const [newCarrier, setNewCarrier] = useState("");
  const [adding, setAdding] = useState(false);
  const [carriers, setCarriers] = useState<{ name: string; slug: string }[]>([]);
  const [filter, setFilter] = useState("all");

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
    if (!newTracking || !newCarrier) return;

    setAdding(true);
    try {
      const res = await fetch("/api/trackings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trackingNumber: newTracking,
          carrierSlug: newCarrier,
        }),
      });

      if (res.ok) {
        setNewTracking("");
        setNewCarrier("");
        fetchTrackings();
      }
    } finally {
      setAdding(false);
    }
  }

  const filtered =
    filter === "all"
      ? trackings
      : trackings.filter((t) => {
          const s = t.status.toLowerCase();
          if (filter === "active") return !s.includes("deliver") && !s.includes("exception");
          if (filter === "delivered") return s.includes("deliver");
          if (filter === "issues") return s.includes("exception") || s.includes("fail");
          return true;
        });

  const stats = {
    total: trackings.length,
    active: trackings.filter((t) => {
      const s = t.status.toLowerCase();
      return !s.includes("deliver") && !s.includes("exception");
    }).length,
    delivered: trackings.filter((t) => t.status.toLowerCase().includes("deliver")).length,
    avgConfidence:
      trackings.filter((t) => t.confidencePct).length > 0
        ? Math.round(
            trackings
              .filter((t) => t.confidencePct)
              .reduce((a, t) => a + (t.confidencePct || 0), 0) /
              trackings.filter((t) => t.confidencePct).length
          )
        : 0,
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-2xl text-cyber-text">Dashboard</h1>
          <p className="text-sm text-cyber-muted font-mono mt-1">
            Your tracked shipments
          </p>
        </div>
        <div className="flex items-center gap-2">
          {sseConnected ? (
            <>
              <Wifi className="w-4 h-4 text-cyber-green" />
              <span className="text-xs text-cyber-green font-mono">LIVE</span>
              {updateCount > 0 && (
                <span className="text-[10px] text-cyber-muted font-mono">
                  ({updateCount} updates)
                </span>
              )}
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4 text-cyber-muted" />
              <span className="text-xs text-cyber-muted font-mono">OFFLINE</span>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Tracked" value={stats.total} color="cyan" />
        <StatCard label="Active" value={stats.active} color="purple" />
        <StatCard label="Delivered" value={stats.delivered} color="green" />
        <StatCard label="Avg Confidence" value={`${stats.avgConfidence}%`} color="yellow" />
      </div>

      <CyberCard terminal title="parcelstats://add-tracking" className="mb-8">
        <form onSubmit={handleAddTracking} className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Enter tracking number..."
              value={newTracking}
              onChange={(e) => setNewTracking(e.target.value)}
              className="cyber-input w-full text-sm"
            />
          </div>
          <select
            value={newCarrier}
            onChange={(e) => setNewCarrier(e.target.value)}
            className="cyber-input text-sm min-w-[160px]"
          >
            <option value="">Select carrier</option>
            {carriers.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={adding || !newTracking || !newCarrier}
            className="cyber-btn-primary cyber-btn whitespace-nowrap"
          >
            {adding ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4 mr-1" />
            )}
            Track
          </button>
        </form>
      </CyberCard>

      <div className="flex items-center gap-2 mb-4">
        {["all", "active", "delivered", "issues"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs font-mono px-3 py-1 rounded border transition-all ${
              filter === f
                ? "border-cyber-cyan/50 bg-cyber-cyan/10 text-cyber-cyan"
                : "border-cyber-border text-cyber-muted hover:text-cyber-text"
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
        <span className="text-xs text-cyber-muted ml-auto font-mono">
          {filtered.length} shipment{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-cyber-cyan animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <CyberCard>
          <div className="text-center py-12">
            <Package className="w-12 h-12 text-cyber-muted/30 mx-auto mb-4" />
            <p className="text-cyber-muted font-mono text-sm">
              {trackings.length === 0
                ? "No shipments tracked yet. Add one above to get started."
                : "No shipments match this filter."}
            </p>
          </div>
        </CyberCard>
      ) : (
        <div className="grid gap-3">
          {filtered.map((t) => (
            <TrackingCard
              key={t.id}
              id={t.id}
              trackingNumber={t.trackingNumber}
              carrier={t.carrier.name}
              carrierSlug={t.carrier.slug}
              status={t.status}
              lastEvent={t.lastEvent ?? undefined}
              lastLocation={t.lastLocation ?? undefined}
              estimatedDelivery={t.estimatedDelivery ?? undefined}
              confidencePct={t.confidencePct ?? undefined}
              updatedAt={t.updatedAt ?? undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}
