"use client";

import { cn, formatStatusLabel, getStatusBadgeClass } from "@/lib/utils";

interface TimelineEvent {
  status: string;
  location?: string;
  description?: string;
  time: string;
  isLatest?: boolean;
}

export function TrackingTimeline({ events }: { events: TimelineEvent[] }) {
  return (
    <div className="cyber-timeline pl-4 space-y-4">
      {events.map((event, i) => (
        <div key={i} className="flex gap-4 relative">
          <div
            className={cn(
              "cyber-timeline-dot shrink-0",
              event.isLatest && "cyber-timeline-dot-active"
            )}
          >
            <div
              className={cn(
                "w-2 h-2 rounded-full",
                event.isLatest ? "bg-cyber-green" : "bg-cyber-cyan"
              )}
            />
          </div>
          <div className="flex-1 min-w-0 pb-2">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-2">
              <div className="min-w-0">
                <p
                  className={cn(
                    "text-sm font-mono font-medium break-words",
                    event.isLatest ? "text-cyber-green" : "text-cyber-text"
                  )}
                >
                  {formatStatusLabel(event.status)}
                </p>
                {event.location && (
                  <p className="text-xs text-cyber-muted break-words">{event.location}</p>
                )}
                {event.description && (
                  <p className="text-xs text-cyber-muted mt-1 break-words">
                    {event.description}
                  </p>
                )}
              </div>
              <span className="text-xs text-cyber-muted font-mono sm:whitespace-nowrap">
                {event.time}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ConfidenceBar({
  value,
  label,
}: {
  value: number;
  label?: string;
}) {
  const getColor = (v: number) => {
    if (v >= 90) return "bg-cyber-green";
    if (v >= 70) return "bg-cyber-cyan";
    if (v >= 50) return "bg-cyber-yellow";
    return "bg-cyber-red";
  };

  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-xs">
          <span className="text-cyber-muted">{label}</span>
          <span className="text-cyber-text font-mono">{value}%</span>
        </div>
      )}
      <div className="confidence-bar">
        <div
          className={cn("confidence-fill", getColor(value))}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={getStatusBadgeClass(status)}>{formatStatusLabel(status)}</span>;
}
