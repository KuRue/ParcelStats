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
  Server,
  AlertTriangle,
  Search,
  Globe,
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
  research: {
    agent_available: boolean;
    model: string | null;
    patterns: { total: number; mined: number; llm_researched: number };
    missing_lanes: number;
    job: ResearchJob | null;
  } | null;
}

interface ResearchJob {
  state: "idle" | "running" | "completed" | "failed";
  action: string | null;
  phase: string;
  message: string;
  current: number;
  total: number;
  candidates: number;
  created: number;
  skipped: number;
  failed: number;
  current_lane: { carrier: string; origin: string; dest: string } | null;
  recent_results: {
    carrier: string | null;
    origin: string | null;
    dest: string | null;
    created: boolean;
    error: string | null;
    message: string | null;
    stops_count: number | null;
  }[];
  started_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}

type AdminAction = "retrain" | "research-missing" | "research-lane";

function formatJobTime(value: string | null): string {
  if (!value) return "Not started";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatJobPhase(value: string): string {
  return value.replace(/_/g, " ");
}

function laneLabel(lane: { carrier: string | null; origin: string | null; dest: string | null }): string {
  return `${lane.carrier ?? "unknown"} ${lane.origin ?? "??"}→${lane.dest ?? "??"}`;
}

export function AdminContent() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [laneCarrier, setLaneCarrier] = useState("");
  const [laneOrigin, setLaneOrigin] = useState("");
  const [laneDest, setLaneDest] = useState("");

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

  const researchJob = model?.research?.job ?? null;
  const researchRunning = researchJob?.state === "running";

  useEffect(() => {
    if (!researchRunning) return;
    const id = window.setInterval(() => {
      loadAll();
    }, 2500);
    return () => window.clearInterval(id);
  }, [loadAll, researchRunning]);

  const runAction = useCallback(
    async (action: AdminAction, extra?: { carrierSlug?: string; originCountry?: string; destCountry?: string }) => {
      setBusy(true);
      setActionMsg(null);
      try {
        const res = await fetch("/api/admin/model", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, ...extra }),
        });
        const body = await res.json();
        const label =
          action === "retrain"
            ? "Retraining"
            : action === "research-missing"
              ? "Researching missing lanes"
              : "Researching lane";
        if (res.ok) {
          await loadAll();
        }
        setActionMsg(
          res.ok
            ? body.job?.message
              ? `${label}: ${body.job.message}`
              : `${label} started (${body.status ?? "ok"})`
            : `Failed: ${body.error ?? res.status}`
        );
      } catch {
        setActionMsg("Failed: network error");
      } finally {
        setBusy(false);
      }
    },
    [loadAll]
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
              No trained model yet. Add real delivered shipments, then retrain.
            </p>
          )}
        </CyberCard>

        <CyberCard terminal title="Prediction Sources">
          <h2 className="text-sm font-display tracking-wide text-cyber-purple mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Prediction volume by model version
          </h2>
          {model?.sourceBreakdown.length ? (
            <div className="space-y-2">
              {model.sourceBreakdown.map((s) => {
                const pct = totalPredictions
                  ? Math.round((s.count / totalPredictions) * 100)
                  : 0;
                return (
                  <div key={s.modelVersion}>
                    <div className="flex justify-between text-xs font-mono mb-1">
                      <span className="text-cyber-cyan">
                        Model {s.modelVersion}
                      </span>
                      <span className="text-cyber-text">
                        {s.count} ({pct}%) · {s.avgConfidence}% conf
                      </span>
                    </div>
                    <div className="h-1.5 bg-cyber-border/30 rounded">
                      <div
                        className="h-full rounded bg-cyber-cyan"
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

      {/* Route Research */}
      <CyberCard terminal title="Route Research" glow="purple" className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-display tracking-wide text-cyber-purple flex items-center gap-2">
            <Globe className="w-4 h-4" />
            Agent status
          </h2>
        </div>

        {model?.research ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <StatCard label="Agent" value={model.research.agent_available ? "Active" : "Off"} color={model.research.agent_available ? "green" : "yellow"} />
              <StatCard label="Route Patterns" value={model.research.patterns.total} color="purple" sub={`${model.research.patterns.mined} mined · ${model.research.patterns.llm_researched} LLM`} />
              <StatCard label="Missing Lanes" value={model.research.missing_lanes} color={model.research.missing_lanes > 0 ? "yellow" : "green"} sub="Active shipments without patterns" />
              <StatCard label="LLM Model" value={model.research.model ?? "N/A"} color="cyan" />
            </div>
            {model.research.job && (
              <div className="mb-4 border-y border-cyber-border/30 py-3">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      {model.research.job.state === "running" && (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-cyber-purple" />
                      )}
                      {model.research.job.state === "failed" && (
                        <AlertTriangle className="h-3.5 w-3.5 text-cyber-red" />
                      )}
                      <p className="font-mono text-sm text-cyber-text">
                        {model.research.job.state === "running"
                          ? "Working"
                          : model.research.job.state === "completed"
                            ? "Last run complete"
                            : model.research.job.state === "failed"
                              ? "Last run failed"
                              : "Idle"}
                      </p>
                      <span className="font-mono text-[10px] uppercase tracking-wide text-cyber-muted">
                        {formatJobPhase(model.research.job.phase)}
                      </span>
                    </div>
                    <p className="mt-1 break-words font-mono text-xs text-cyber-muted">
                      {model.research.job.message}
                    </p>
                    {model.research.job.current_lane && (
                      <p className="mt-1 font-mono text-xs text-cyber-purple">
                        Current lane: {laneLabel(model.research.job.current_lane)}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0 font-mono text-[11px] text-cyber-muted md:text-right">
                    <p>Started {formatJobTime(model.research.job.started_at)}</p>
                    <p>Updated {formatJobTime(model.research.job.updated_at)}</p>
                  </div>
                </div>

                {model.research.job.total > 0 && (
                  <div className="mt-3">
                    <div className="mb-1 flex justify-between font-mono text-[11px] text-cyber-muted">
                      <span>
                        {model.research.job.current} / {model.research.job.total} lanes
                      </span>
                      <span>
                        {Math.round(
                          (model.research.job.current / model.research.job.total) * 100
                        )}
                        %
                      </span>
                    </div>
                    <div className="h-1.5 bg-cyber-border/30">
                      <div
                        className="h-full bg-cyber-purple transition-all"
                        style={{
                          width: `${Math.min(
                            100,
                            Math.round(
                              (model.research.job.current / model.research.job.total) * 100
                            )
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

                <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-xs md:grid-cols-4">
                  <div>
                    <p className="text-cyber-muted">Candidates</p>
                    <p className="text-cyber-text">{model.research.job.candidates}</p>
                  </div>
                  <div>
                    <p className="text-cyber-muted">Created</p>
                    <p className="text-cyber-green">{model.research.job.created}</p>
                  </div>
                  <div>
                    <p className="text-cyber-muted">Skipped</p>
                    <p className="text-cyber-yellow">{model.research.job.skipped}</p>
                  </div>
                  <div>
                    <p className="text-cyber-muted">Failed</p>
                    <p className="text-cyber-red">{model.research.job.failed}</p>
                  </div>
                </div>

                {model.research.job.recent_results.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {model.research.job.recent_results.map((result, index) => (
                      <div
                        key={`${result.carrier}-${result.origin}-${result.dest}-${index}`}
                        className="flex flex-col gap-1 border-t border-cyber-border/20 pt-1 font-mono text-[11px] sm:flex-row sm:items-center sm:justify-between"
                      >
                        <span className="text-cyber-text">
                          {laneLabel(result)}
                        </span>
                        <span
                          className={
                            result.error
                              ? "text-cyber-red"
                              : result.created
                                ? "text-cyber-green"
                                : "text-cyber-muted"
                          }
                        >
                          {result.error
                            ? result.error
                            : result.created
                              ? `created ${result.stops_count ?? "?"} stops`
                              : result.message ?? "already covered"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <p className="text-xs text-cyber-muted font-mono mb-4">
            Agent status unavailable.
          </p>
        )}

        {actionMsg && (
          <p className="text-xs font-mono text-cyber-yellow mb-3">{actionMsg}</p>
        )}

        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => runAction("research-missing")}
            disabled={busy}
            className="cyber-btn text-xs disabled:opacity-50"
          >
            <Search className="w-3 h-3 mr-1 inline" />
            Research Missing
          </button>
        </div>

        <div className="border-t border-cyber-border/30 pt-4">
          <p className="text-xs text-cyber-muted font-mono mb-2">
            Research a specific lane:
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              value={laneCarrier}
              onChange={(e) => setLaneCarrier(e.target.value)}
              placeholder="Carrier slug (e.g. speedpak)"
              className="cyber-input text-xs w-32"
            />
            <input
              value={laneOrigin}
              onChange={(e) => setLaneOrigin(e.target.value)}
              placeholder="Origin (e.g. CN)"
              className="cyber-input text-xs w-20"
            />
            <input
              value={laneDest}
              onChange={(e) => setLaneDest(e.target.value)}
              placeholder="Dest (e.g. US)"
              className="cyber-input text-xs w-20"
            />
            <button
              onClick={() => {
                if (laneCarrier && laneOrigin && laneDest) {
                  runAction("research-lane", {
                    carrierSlug: laneCarrier,
                    originCountry: laneOrigin,
                    destCountry: laneDest,
                  });
                }
              }}
              disabled={busy || !laneCarrier || !laneOrigin || !laneDest}
              className="cyber-btn text-xs disabled:opacity-50"
            >
              Research Lane
            </button>
          </div>
        </div>
      </CyberCard>

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
                    <span className="text-cyber-muted">{v}</span>
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
