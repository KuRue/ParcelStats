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
        "bg-cyber-card border border-cyber-border rounded-lg relative overflow-hidden",
        glowClasses[glow],
        className
      )}
    >
      {terminal && (
        <div className="terminal-header">
          <div className="terminal-dot bg-cyber-red" />
          <div className="terminal-dot bg-cyber-yellow" />
          <div className="terminal-dot bg-cyber-green" />
          {title && (
            <span className="text-xs text-cyber-muted font-mono ml-2">
              {title}
            </span>
          )}
        </div>
      )}
      <div className="relative z-10 p-4">{children}</div>
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
      <div className="text-center">
        <p className={cn("text-2xl font-display font-bold", colorMap[color])}>
          {value}
        </p>
        <p className="stat-label mt-1">{label}</p>
        {sub && <p className="text-xs text-cyber-muted mt-1">{sub}</p>}
      </div>
    </CyberCard>
  );
}
