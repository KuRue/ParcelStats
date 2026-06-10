"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CyberCardProps {
  children: ReactNode;
  className?: string;
  glow?: "cyan" | "green" | "purple" | "none";
  terminal?: boolean;
  title?: string;
}

export function CyberCard({
  children,
  className,
  glow = "none",
  terminal = false,
  title,
}: CyberCardProps) {
  const glowClasses = {
    cyan: "border-cyber-cyan/30 shadow-cyber-glow",
    green: "border-cyber-green/30 shadow-cyber-glow-green",
    purple: "border-cyber-purple/30 shadow-cyber-glow-purple",
    none: "",
  };

  return (
    <div
      className={cn(
        "bg-cyber-card/95 border border-cyber-border rounded-lg relative overflow-hidden shadow-sm",
        glowClasses[glow],
        className
      )}
    >
      {(terminal || title) && title && (
        <div className="panel-header">
          <div className="h-4 w-1 rounded-full bg-cyber-cyan/70" />
          <span className="panel-title">
            {title}
          </span>
        </div>
      )}
      <div className="relative z-10 p-3 sm:p-4">{children}</div>
    </div>
  );
}

export function StatCard({
  label,
  value,
  sub,
  color = "cyan",
}: {
  label: string;
  value: string | number;
  sub?: string;
  color?: "cyan" | "green" | "purple" | "yellow" | "red";
}) {
  const colorMap = {
    cyan: "text-cyber-cyan",
    green: "text-cyber-green",
    purple: "text-cyber-purple",
    yellow: "text-cyber-yellow",
    red: "text-cyber-red",
  };

  return (
    <CyberCard>
      <div className="text-center min-w-0">
        <p
          className={cn(
            "text-xl sm:text-2xl leading-tight font-display font-bold break-words",
            colorMap[color]
          )}
        >
          {value}
        </p>
        <p className="stat-label mt-1">{label}</p>
        {sub && <p className="text-xs text-cyber-muted mt-1">{sub}</p>}
      </div>
    </CyberCard>
  );
}
