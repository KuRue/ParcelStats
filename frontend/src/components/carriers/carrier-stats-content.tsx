"use client";

import { useState, useEffect } from "react";
import { CyberCard, StatCard } from "@/components/ui/cyber-card";
import { Plane, Loader2, TrendingUp, Clock, CheckCircle, Package } from "lucide-react";
interface CarrierStat {
  slug: string;
  name: string;
  total_shipments: number;
  delivered: number;
  active: number;
  avg_transit_days: number | null;
  median_transit_days: number | null;
  on_time_pct: number | null;
  fastest_days: number | null;
  slowest_days: number | null;
  top_lanes: string[];
}

export function CarrierStatsContent() {
  const [carriers, setCarriers] = useState<CarrierStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/carriers")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.carriers) setCarriers(data.carriers);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-cyber-cyan animate-spin" />
      </div>
    );
  }

  const totalDelivered = carriers.reduce((s, c) => s + c.delivered, 0);
  const totalActive = carriers.reduce((s, c) => s + c.active, 0);
  const allTransit = carriers
    .filter((c) => c.avg_transit_days)
    .map((c) => c.avg_transit_days!);
  const overallAvg = allTransit.length
    ? (allTransit.reduce((a, b) => a + b, 0) / allTransit.length).toFixed(1)
    : "?";
  const onTimeCarriers = carriers.filter((c) => c.on_time_pct !== null);
  const overallOnTime = onTimeCarriers.length
    ? Math.round(onTimeCarriers.reduce((s, c) => s + (c.on_time_pct || 0), 0) / onTimeCarriers.length)
    : null;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 md:py-8 pb-24 md:pb-8">
      <div className="flex items-center gap-2 mb-6">
        <Plane className="w-6 h-6 text-cyber-cyan" />
        <h1 className="font-display text-xl font-bold text-cyber-cyan text-shadow-cyber">
          Carrier Reliability
        </h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Delivered" value={totalDelivered} color="green" />
        <StatCard label="Active Shipments" value={totalActive} color="cyan" />
        <StatCard label="Avg Transit Days" value={overallAvg} color="purple" />
        <StatCard
          label="On-Time Rate"
          value={overallOnTime !== null ? `${overallOnTime}%` : "?"}
          color={overallOnTime !== null && overallOnTime >= 80 ? "green" : "yellow"}
        />
      </div>

      {carriers.length === 0 ? (
        <CyberCard>
          <p className="text-center font-mono text-sm text-cyber-muted py-8">
            No carrier data yet. Track some shipments to build reliability scores.
          </p>
        </CyberCard>
      ) : (
        <div className="space-y-4">
          {carriers.map((c) => (
            <CyberCard key={c.slug} className="hover:border-cyber-cyan/40 transition-colors">
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-display text-base font-bold text-cyber-text">
                      {c.name}
                    </h3>
                    <span className="font-mono text-[10px] uppercase text-cyber-muted border border-cyber-border rounded px-1.5 py-0.5">
                      {c.slug}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-cyber-muted font-mono">Delivered</p>
                      <p className="font-display text-lg font-bold text-cyber-green">{c.delivered}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-cyber-muted font-mono">Active</p>
                      <p className="font-display text-lg font-bold text-cyber-cyan">{c.active}</p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-cyber-muted font-mono">Avg Transit</p>
                      <p className="font-display text-lg font-bold text-cyber-purple">
                        {c.avg_transit_days ? `${c.avg_transit_days}d` : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-cyber-muted font-mono">On-Time</p>
                      <p className={`font-display text-lg font-bold ${
                        c.on_time_pct === null ? "text-cyber-muted"
                        : c.on_time_pct >= 80 ? "text-cyber-green"
                        : c.on_time_pct >= 60 ? "text-cyber-yellow"
                        : "text-cyber-red"
                      }`}>
                        {c.on_time_pct !== null ? `${c.on_time_pct}%` : "—"}
                      </p>
                    </div>
                  </div>

                  {c.fastest_days && c.slowest_days && (
                    <p className="font-mono text-xs text-cyber-muted">
                      Range: {c.fastest_days}d – {c.slowest_days}d
                      {c.median_transit_days ? ` · Median: ${c.median_transit_days}d` : ""}
                    </p>
                  )}

                  {c.top_lanes.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {c.top_lanes.map((lane) => (
                        <span
                          key={lane}
                          className="font-mono text-[10px] text-cyber-cyan bg-cyber-cyan/10 border border-cyber-cyan/20 rounded px-1.5 py-0.5"
                        >
                          {lane}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {c.delivered > 0 && (
                  <div className="shrink-0">
                    <ReliabilityBar
                      onTimePct={c.on_time_pct}
                      delivered={c.delivered}
                    />
                  </div>
                )}
              </div>
            </CyberCard>
          ))}
        </div>
      )}
    </div>
  );
}

function ReliabilityBar({ onTimePct, delivered }: { onTimePct: number | null; delivered: number }) {
  const pct = onTimePct ?? 0;
  const color = pct >= 80 ? "#39ff14" : pct >= 60 ? "#ffdd00" : "#ff003c";
  const confidence = Math.min(100, delivered * 5);

  return (
    <div className="w-24 text-center">
      <div className="relative h-20 w-3 bg-cyber-border/30 rounded-full mx-auto overflow-hidden">
        <div
          className="absolute bottom-0 left-0 right-0 rounded-full transition-all"
          style={{ height: `${pct}%`, background: color, boxShadow: `0 0 8px ${color}80` }}
        />
      </div>
      <p className="font-mono text-[9px] text-cyber-muted mt-1">
        {delivered < 5 ? "Low data" : `${confidence}% confidence`}
      </p>
    </div>
  );
}
