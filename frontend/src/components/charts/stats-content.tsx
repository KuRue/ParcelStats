"use client";

import { useState, useEffect } from "react";
import { CyberCard, StatCard } from "@/components/ui/cyber-card";
import { ConfidenceBar } from "@/components/tracking/timeline";
import {
  Globe,
  Package,
  Brain,
  TrendingUp,
  Activity,
  Loader2,
  BarChart3,
} from "lucide-react";

interface CommunityStats {
  totalShipments: number;
  totalCarriers: number;
  totalPredictions: number;
  avgConfidence: number;
  topCarriers: { name: string; slug: string; count: number; avgDays: number }[];
  routeStats: {
    route: string;
    avgDays: number;
    sampleCount: number;
  }[];
}

export function StatsContent() {
  const [stats, setStats] = useState<CommunityStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/predictions/community-stats")
      .then((r) => (r.ok ? r.json() : null))
      .then(setStats)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-cyber-cyan animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="font-display text-2xl text-cyber-text">
          Community Stats
        </h1>
        <p className="text-sm text-cyber-muted font-mono mt-1">
          Aggregated tracking intelligence from the community
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Shipments Tracked"
          value={stats?.totalShipments ?? 0}
          color="cyan"
          sub="All time"
        />
        <StatCard
          label="Carriers Active"
          value={stats?.totalCarriers ?? 0}
          color="green"
          sub="International"
        />
        <StatCard
          label="Predictions Made"
          value={stats?.totalPredictions ?? 0}
          color="purple"
          sub="AI powered"
        />
        <StatCard
          label="Avg Confidence"
          value={`${stats?.avgConfidence ?? 0}%`}
          color="yellow"
          sub="Across all routes"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <CyberCard terminal title="stats://carrier-performance">
          <h2 className="text-sm font-display uppercase tracking-wider text-cyber-cyan mb-4 flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Carrier Performance
          </h2>

          {!stats?.topCarriers.length ? (
            <div className="text-center py-8">
              <Package className="w-8 h-8 text-cyber-muted/30 mx-auto mb-2" />
              <p className="text-xs text-cyber-muted font-mono">
                No carrier data yet. Start tracking to build stats.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {stats.topCarriers.map((carrier) => (
                <div
                  key={carrier.slug}
                  className="flex items-center justify-between py-2 border-b border-cyber-border/30 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <Package className="w-3 h-3 text-cyber-cyan" />
                    <span className="text-sm text-cyber-text font-mono">
                      {carrier.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-cyber-muted font-mono">
                      {carrier.count} shipments
                    </span>
                    <span className="text-sm text-cyber-cyan font-mono">
                      {carrier.avgDays.toFixed(1)}d avg
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CyberCard>

        <CyberCard terminal title="stats://route-analysis">
          <h2 className="text-sm font-display uppercase tracking-wider text-cyber-purple mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Popular Routes
          </h2>

          {!stats?.routeStats.length ? (
            <div className="text-center py-8">
              <Globe className="w-8 h-8 text-cyber-muted/30 mx-auto mb-2" />
              <p className="text-xs text-cyber-muted font-mono">
                No route data yet. Track more shipments to populate.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {stats.routeStats.map((route, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between py-2 border-b border-cyber-border/30 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <Activity className="w-3 h-3 text-cyber-purple" />
                    <span className="text-sm text-cyber-text font-mono">
                      {route.route}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-cyber-muted font-mono">
                      n={route.sampleCount}
                    </span>
                    <span className="text-sm text-cyber-purple font-mono">
                      {route.avgDays.toFixed(1)}d
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CyberCard>
      </div>

      <CyberCard className="mt-6">
        <div className="text-center py-6">
          <Brain className="w-10 h-10 text-cyber-cyan/40 mx-auto mb-3" />
          <p className="text-sm text-cyber-muted font-mono">
            Every tracked shipment improves our AI predictions.
          </p>
          <p className="text-xs text-cyber-muted/60 font-mono mt-1">
            More data = tighter confidence intervals = better ETAs
          </p>
        </div>
      </CyberCard>
    </div>
  );
}
