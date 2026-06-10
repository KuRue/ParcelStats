import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatConfidence(pct: number): {
  label: string;
  color: string;
} {
  if (pct >= 90) return { label: "Very High", color: "text-cyber-green" };
  if (pct >= 70) return { label: "High", color: "text-cyber-cyan" };
  if (pct >= 50) return { label: "Moderate", color: "text-cyber-yellow" };
  if (pct >= 30) return { label: "Low", color: "text-cyber-orange" };
  return { label: "Very Low", color: "text-cyber-red" };
}

export function formatStatusLabel(status: string): string {
  if (!status) return "Unknown";

  const normalized = status
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function normalizedStatus(status: string): string {
  return status.toLowerCase().replace(/[_-]+/g, " ");
}

export function getStatusColor(status: string): string {
  const s = normalizedStatus(status);
  if (s.includes("deliver") && s.includes("fail")) return "text-cyber-red";
  if (s.includes("deliver")) return "text-cyber-green";
  if (s.includes("transit")) return "text-cyber-cyan";
  if (s.includes("custom")) return "text-cyber-yellow";
  if (s.includes("out for delivery")) return "text-cyber-purple";
  if (s.includes("exception")) return "text-cyber-red";
  if (s.includes("pending") || s.includes("label")) return "text-cyber-muted";
  return "text-cyber-text";
}

export function getStatusBadgeClass(status: string): string {
  const s = normalizedStatus(status);
  if (s.includes("deliver") && !s.includes("fail")) return "cyber-badge-success";
  if (s.includes("exception") || s.includes("fail")) return "cyber-badge-danger";
  if (s.includes("custom")) return "cyber-badge-warning";
  if (s.includes("transit") || s.includes("out for delivery")) return "cyber-badge-info";
  return "cyber-badge";
}
