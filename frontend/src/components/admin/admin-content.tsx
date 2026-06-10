"use client";

import { useState, useEffect, useCallback } from "react";
import { CyberCard, StatCard } from "@/components/ui/cyber-card";
import {
  Users,
  Package,
  Brain,
  Activity,
  Loader2,
  RefreshCw,
  Database,
  Server,
  AlertTriangle,
} from "lucide-react";

interface AdminStats {
  users: { total: number; newThisWeek: number };
  shipments: {
    total: number;
    newThisWeek: number;
    active: number;
    delivered: number;
  };
  statusBreakdown: { status: string; count: number }[];
  sourceBreakdown: { source: string; count: number }[];
  shipmentsPerDay: { day: string; count: number }[];
  predictions: { total: number };
  topUsers: { name: string; email: string; shipmentCount: number }[];
  mlHealth: {
    status: string;
    worker: {
      running: boolean;
      processed: number;
      failed: number;
      queue_size: number;
      scraper_health: Record<
        string,
        {
          jobs_in_window: number;
          success_rate: number | null;
          degraded: boolean;
          last_error: string | null;
        }
      >;
    };
    scheduler: { running: boolean; polls_done: number; jobs_enqueued: number };
  } | null;
}

interface AccuracyBucket {
  count: number;
  mae_days?: number;
  bias_days?: number;
  within_1_day_pct?: number;
  within_2_days_pct?: number;
}

interface ModelInfo {
  sourceBreakdown: {
    modelVersion: string;
    count: number;
    avgConfidence: number;
  }[];
  models:
    | {
        name: string;
        version: string;
        trained_at: string | null;
        metrics: Record<string, number> | null;
      }[]
    | null;
  accuracy: {
    overall: AccuracyBucket;
    by_model: Record<string, AccuracyBucket>;
    by_carrier: Record<string, AccuracyBucket>;
  } | null;
}

const FALLBACK_LABELS: Record<string, string> = {
  fallback_route_stats: "Route stats fallback",
  carrier_estimate: "Carrier estimate",
  baseline_eta: "Baseline heuristic",
};

export function AdminContent() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    const [statsRes, modelRes] = await Promise.all([
      fetch("/api/admin/stats").then((r) => (r.ok ? r.json() : null)),
      fetch("/api/admin/model").then((r) => (r.ok ? r.json() : null)),
    ]);
    setStats(statsRes);
    setModel(modelRes);
  }, []);

  useEffect(() => {
    loadAll().finally(() => setLoading(false));
  }, [loadAll]);

  const runAction = useCallback(
    async (action: "retrain" | "seed") => {
      if (
        action === "seed" &&
        !window.confirm(
          "Seed 2000 synthetic shipments into the database for training?"
        )
      ) {
        return;
      }
      setBusy(true);
      setActionMsg(null);
      try {
        const res = await fetch("/api/admin/model", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action }),
        });
        const body = await res.json();
        setActionMsg(
          res.ok
            ? `${action === "retrain" ? "Retraining" : "Seeding"} started (${body.status ?? "ok"})`
            : `Failed: ${body.error ?? res.status}`
        );
      } catch {
        setActionMsg("Failed: network error");
      } finally {
        setBusy(false);
      }
    },
    []
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-cyber-cyan animate-spin" />
      </div>
    );
  }

  const maxPerDay = Math.max(
    1,
    ...(stats?.shipmentsPerDay.map((d) => d.count) ?? [1])
  );
  const totalPredictions = model?.sourceBreakdown.reduce(
    (acc, s) => acc + s.count,
    0
  );

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 md:py-8 pb-24 md:pb-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl text-cyber-text">
            Admin Dashboard
          </h1>
          <p className="text-sm text-cyber-muted font-mono mt-1">
            System overview and model operations
          </p>
        </div>
        <button
          onClick={() => loadAll()}
          className="cyber-btn text-xs"
          aria-label="Refresh"
        >
          <RefreshCw className="w-3 h-3 mr-1 inline" />
          Refresh
        </button>
      </div>

      {/* Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Users"
          value={stats?.users.total ?? 0}
          color="cyan"
          sub={`+${stats?.users.newThisWeek ?? 0} this week`}
        />
        <StatCard
          label="Shipments"
          value={stats?.shipments.total ?? 0}
          color="green"
          sub={`+${stats?.shipments.newThisWeek ?? 0} this week`}
        />
        <StatCard
          label="In Transit"
          value={stats?.shipments.active ?? 0}
          color="purple"
          sub={`${stats?.shipments.delivered ?? 0} delivered`}
        />
        <StatCard
          label="Predictions"
          value={stats?.predictions.total ?? 0}
          color="yellow"
          sub="All time"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <CyberCard terminal title="Shipments / Day (14d)">
          <div className="flex items-end gap-1 h-28">
            {stats?.shipmentsPerDay.map((d) => (
              <div
                key={d.day}
                className="flex-1 bg-cyber-cyan/60 hover:bg-cyber-cyan rounded-t"
                style={{ height: `${(d.count / maxPerDay) * 100}%` }}
                title={`${d.day}: ${d.count}`}
              />
            ))}
            {!stats?.shipmentsPerDay.length && (
              <p className="text-xs text-cyber-muted font-mono">
                No shipments in the last 14 days
              </p>
            )}
          </div>
        </CyberCard>

        <CyberCard terminal title="Status & Source">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              {stats?.statusBreakdown.slice(0, 7).map((s) => (
                <div key={s.status} className="flex justify-between text-xs font-mono">
                  <span className="text-cyber-muted truncate">{s.status}</span>
                  <span className="text-cyber-cyan ml-2">{s.count}</span>
                </div>
              ))}
            </div>
            <div className="space-y-1">
              {stats?.sourceBreakdown.map((s) => (
                <div key={s.source} className="flex justify-between text-xs font-mono">
                  <span className="text-cyber-muted">{s.source}</span>
                  <span className="text-cyber-purple ml-2">{s.count}</span>
                </div>
              ))}
            </div>
          </div>
        </CyberCard>
      </div>

      {/* System health */}
      <CyberCard terminal title="System Health" className="mb-6">
        {stats?.mlHealth ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-cyber-green" />
              <div>
                <p className="text-xs text-cyber-muted font-mono">ML Service</p>
                <p className="text-sm text-cyber-green font-mono">
                  {stats.mlHealth.status === "ok" ? "Online" : stats.mlHealth.status}
                </p>
              </div>
            </div>
            <div>
              <p className="text-xs text-cyber-muted font-mono">Worker</p>
              <p className="text-sm font-mono text-cyber-text">
                {stats.mlHealth.worker.processed} done /{" "}
                <span className="text-cyber-red">
                  {stats.mlHealth.worker.failed} failed
                </span>
              </p>
            </div>
            <div>
              <p className="text-xs text-cyber-muted font-mono">Queue</p>
              <p className="text-sm font-mono text-cyber-text">
                {stats.mlHealth.worker.queue_size} jobs
              </p>
            </div>
            <div>
              <p className="text-xs text-cyber-muted font-mono">Scheduler</p>
              <p className="text-sm font-mono text-cyber-text">
                {stats.mlHealth.scheduler.polls_done} polls,{" "}
                {stats.mlHealth.scheduler.jobs_enqueued} enqueued
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-cyber-red">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-sm font-mono">ML service unreachable</span>
          </div>
        )}

        {stats?.mlHealth?.worker.scraper_health &&
          Object.keys(stats.mlHealth.worker.scraper_health).length > 0 && (
            <div className="mt-4 pt-4 border-t border-cyber-border/30 space-y-1">
              {Object.entries(stats.mlHealth.worker.scraper_health).map(
                ([slug, h]) => (
                  <div
                    key={slug}
                    className="flex items-center justify-between text-xs font-mono"
                  >
                    <span
                      className={h.degraded ? "text-cyber-red" : "text-cyber-muted"}
                    >
                      {h.degraded && "⚠ "}
                      {slug}
                    </span>
                    <span className="text-cyber-text">
                      {h.success_rate !== null
                        ? `${Math.round(h.success_rate * 100)}% ok`
                        : `${h.jobs_in_window} jobs`}
                      {h.last_error && (
                        <span className="text-cyber-red/70 ml-2">
                          {h.last_error.slice(0, 60)}
                        </span>
                      )}
                    </span>
                  </div>
                )
              )}
            </div>
          )}
      </CyberCard>

      {/* AI model */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <CyberCard terminal title="AI Model" glow="cyan">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-display tracking-wide text-cyber-cyan flex items-center gap-2">
              <Brain className="w-4 h-4" />
              Model versions
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => runAction("retrain")}
                disabled={busy}
                className="cyber-btn text-xs disabled:opacity-50"
              >
                <RefreshCw className="w-3 h-3 mr-1 inline" />
                Retrain
              </button>
              <button
                onClick={() => runAction("seed")}
                disabled={busy}
                className="cyber-btn text-xs disabled:opacity-50"
              >
                <Database className="w-3 h-3 mr-1 inline" />
                Seed Data
              </button>
            </div>
          </div>

          {actionMsg && (
            <p className="text-xs font-mono text-cyber-yellow mb-3">{actionMsg}</p>
          )}

          {model?.models?.length ? (
            <div className="space-y-2">
              {model.models.map((m) => (
                <div
                  key={`${m.name}-${m.version}`}
                  className="py-2 border-b border-cyber-border/30 last:border-0"
                >
                  <div className="flex justify-between text-sm font-mono">
                    <span className="text-cyber-text">{m.name}</span>
                    <span className="text-cyber-cyan">{m.version}</span>
                  </div>
                  <div className="flex justify-between text-xs font-mono text-cyber-muted">
                    <span>
                      {m.trained_at
                        ? new Date(m.trained_at).toLocaleString()
                        : "unknown"}
                    </span>
                    {m.metrics && (
                      <span>
                        {Object.entries(m.metrics)
                          .slice(0, 3)
                          .map(([k, v]) =>
                            `${k}: ${typeof v === "number" ? v.toFixed(2) : v}`
                          )
                          .join("  ")}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-cyber-muted font-mono">
              No trained model yet. Seed data and retrain to bootstrap.
            </p>
          )}
        </CyberCard>

        <CyberCard terminal title="Prediction Sources">
          <h2 className="text-sm font-display tracking-wide text-cyber-purple mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Who answered: model vs fallbacks
          </h2>
          {model?.sourceBreakdown.length ? (
            <div className="space-y-2">
              {model.sourceBreakdown.map((s) => {
                const isModel = !FALLBACK_LABELS[s.modelVersion];
                const pct = totalPredictions
                  ? Math.round((s.count / totalPredictions) * 100)
                  : 0;
                return (
                  <div key={s.modelVersion}>
                    <div className="flex justify-between text-xs font-mono mb-1">
                      <span className={isModel ? "text-cyber-cyan" : "text-cyber-muted"}>
                        {FALLBACK_LABELS[s.modelVersion] ?? `Model ${s.modelVersion}`}
                      </span>
                      <span className="text-cyber-text">
                        {s.count} ({pct}%) · {s.avgConfidence}% conf
                      </span>
                    </div>
                    <div className="h-1.5 bg-cyber-border/30 rounded">
                      <div
                        className={`h-full rounded ${isModel ? "bg-cyber-cyan" : "bg-cyber-purple/60"}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-cyber-muted font-mono">No predictions yet.</p>
          )}
        </CyberCard>
      </div>

      {/* Accuracy + top users */}
      <div className="grid lg:grid-cols-2 gap-6">
        <CyberCard terminal title="Model Accuracy">
          {model?.accuracy && model.accuracy.overall.count > 0 ? (
            <div>
              <div className="grid grid-cols-3 gap-3 mb-4">
                <StatCard
                  label="Scored"
                  value={model.accuracy.overall.count}
                  color="cyan"
                />
                <StatCard
                  label="Avg Error"
                  value={`${model.accuracy.overall.mae_days ?? 0}d`}
                  color="green"
                />
                <StatCard
                  label="Within 1d"
                  value={`${model.accuracy.overall.within_1_day_pct ?? 0}%`}
                  color="purple"
                />
              </div>
              <div className="space-y-1">
                {Object.entries(model.accuracy.by_model).map(([v, b]) => (
                  <div key={v} className="flex justify-between text-xs font-mono">
                    <span className="text-cyber-muted">
                      {FALLBACK_LABELS[v] ?? v}
                    </span>
                    <span className="text-cyber-text">
                      ±{b.mae_days ?? 0}d over {b.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-cyber-muted font-mono">
              No delivered shipments with predictions yet — accuracy appears
              after first deliveries.
            </p>
          )}
        </CyberCard>

        <CyberCard terminal title="Top Users">
          <h2 className="text-sm font-display tracking-wide text-cyber-green mb-4 flex items-center gap-2">
            <Users className="w-4 h-4" />
            By shipments tracked
          </h2>
          <div className="space-y-1">
            {stats?.topUsers.map((u) => (
              <div
                key={u.email}
                className="flex justify-between text-xs font-mono py-1 border-b border-cyber-border/30 last:border-0"
              >
                <span className="text-cyber-text truncate">
                  {u.name}{" "}
                  <span className="text-cyber-muted/60">{u.email}</span>
                </span>
                <span className="text-cyber-green ml-2 shrink-0">
                  <Package className="w-3 h-3 inline mr-1" />
                  {u.shipmentCount}
                </span>
              </div>
            ))}
          </div>
        </CyberCard>
      </div>
    </div>
  );
}
