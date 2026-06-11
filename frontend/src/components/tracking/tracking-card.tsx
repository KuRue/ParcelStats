"use client";

import { CyberCard } from "@/components/ui/cyber-card";
import { ConfidenceBar, StatusBadge } from "@/components/tracking/timeline";
import { formatRegionalDateHour, isDeliveredStatus, normalizedStatus } from "@/lib/utils";
import { Package, Clock, MapPin, ExternalLink } from "lucide-react";
import Link from "next/link";

interface TrackingCardProps {
  id: string;
  trackingNumber: string;
  carrier: string;
  carrierSlug: string;
  status: string;
  lastEvent?: string;
  lastLocation?: string;
  estimatedDelivery?: string;
  confidencePct?: number;
  predictionSource?: string | null;
  updatedAt?: string;
}

export function TrackingCard({
  id,
  trackingNumber,
  carrier,
  carrierSlug,
  status,
  lastEvent,
  lastLocation,
  estimatedDelivery,
  confidencePct,
  predictionSource,
  updatedAt,
}: TrackingCardProps) {
  return (
    <Link href={`/track/${id}`}>
      <CyberCard
        glow={
          isDeliveredStatus(status)
            ? "green"
            : normalizedStatus(status).includes("transit")
            ? "cyan"
            : "none"
        }
        className="hover:border-cyber-cyan/40 transition-all duration-200 cursor-pointer group"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <Package className="w-4 h-4 text-cyber-cyan shrink-0" />
              <span className="min-w-0 text-sm font-mono text-cyber-text break-all sm:truncate">
                {trackingNumber}
              </span>
              <span className="text-xs text-cyber-muted font-mono break-words">
                {carrier}
              </span>
            </div>

            <div className="flex items-center gap-2 mb-2">
              <StatusBadge status={status} />
            </div>

            {lastEvent && (
              <p className="text-xs text-cyber-muted mb-1 break-words">{lastEvent}</p>
            )}
            {lastLocation && (
              <div className="flex items-start gap-1 text-xs text-cyber-muted/70">
                <MapPin className="w-3 h-3 shrink-0 mt-0.5" />
                <span className="break-words">{lastLocation}</span>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end sm:gap-2 sm:shrink-0">
            {estimatedDelivery && (
              <div className="text-left sm:text-right">
                <div className="flex items-center gap-1 text-xs text-cyber-muted">
                  <Clock className="w-3 h-3" />
                  <span>ETA</span>
                </div>
                <p className="text-sm font-mono text-cyber-cyan">
                  {formatRegionalDateHour(estimatedDelivery)}
                </p>
              </div>
            )}

            {confidencePct !== undefined && (
              <div className="flex items-center gap-1.5 shrink-0">
                <div className="w-20">
                  <ConfidenceBar value={confidencePct} />
                </div>
                {predictionSource && (
                  <span className="text-[9px] font-mono text-cyber-muted/50 border border-cyber-border/30 rounded px-1">
                    {predictionSource === "knowledge+lanes"
                      ? "CAL"
                      : predictionSource === "knowledge"
                        ? "KB"
                        : "ML"}
                  </span>
                )}
              </div>
            )}

            <ExternalLink className="w-4 h-4 text-cyber-muted group-hover:text-cyber-cyan transition-colors" />
          </div>
        </div>

        {updatedAt && (
          <div className="mt-2 pt-2 border-t border-cyber-border/50">
            <span className="text-[10px] text-cyber-muted/60 font-mono">
              Updated {updatedAt}
            </span>
          </div>
        )}
      </CyberCard>
    </Link>
  );
}
