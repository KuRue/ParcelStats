"use client";

import { CyberCard } from "@/components/ui/cyber-card";
import { ConfidenceBar, StatusBadge } from "@/components/tracking/timeline";
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
  updatedAt,
}: TrackingCardProps) {
  return (
    <Link href={`/track/${id}`}>
      <CyberCard
        glow={
          status.toLowerCase().includes("delivered")
            ? "green"
            : status.toLowerCase().includes("transit")
            ? "cyan"
            : "none"
        }
        className="hover:border-cyber-cyan/40 transition-all duration-200 cursor-pointer group"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <Package className="w-4 h-4 text-cyber-cyan shrink-0" />
              <span className="text-sm font-mono text-cyber-text truncate">
                {trackingNumber}
              </span>
              <span className="text-xs text-cyber-muted font-mono">
                {carrier}
              </span>
            </div>

            <div className="flex items-center gap-2 mb-2">
              <StatusBadge status={status} />
            </div>

            {lastEvent && (
              <p className="text-xs text-cyber-muted mb-1">{lastEvent}</p>
            )}
            {lastLocation && (
              <div className="flex items-center gap-1 text-xs text-cyber-muted/70">
                <MapPin className="w-3 h-3" />
                <span>{lastLocation}</span>
              </div>
            )}
          </div>

          <div className="flex flex-col items-end gap-2 shrink-0">
            {estimatedDelivery && (
              <div className="text-right">
                <div className="flex items-center gap-1 text-xs text-cyber-muted">
                  <Clock className="w-3 h-3" />
                  <span>ETA</span>
                </div>
                <p className="text-sm font-mono text-cyber-cyan">
                  {estimatedDelivery}
                </p>
              </div>
            )}

            {confidencePct !== undefined && (
              <div className="w-24">
                <ConfidenceBar value={confidencePct} />
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
