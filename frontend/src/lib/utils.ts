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

export function formatRegionalDateHour(value: string | Date | null | undefined): string {
  if (!value) return "";

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
  }).format(date);
}

export function normalizedStatus(status: string): string {
  return status.toLowerCase().replace(/[_-]+/g, " ");
}

const NON_FINAL_DELIVERY_TERMS = [
  "out for delivery",
  "delivery attempt",
  "attempted delivery",
  "warehouse",
  "facility",
  "hub",
  "sorting",
  "distribution",
  "customs",
  "carrier",
  "partner",
  "agent",
  "post office",
  "service point",
  "pickup point",
  "collection point",
];

export function isIssueStatus(status: string): boolean {
  const s = normalizedStatus(status);
  return (
    s.includes("exception") ||
    s.includes("fail") ||
    s.includes("error") ||
    s.includes("auth") ||
    s.includes("required") ||
    s.includes("not found") ||
    s.includes("blocked") ||
    s.includes("unavailable")
  );
}

export function isDeliveredStatus(status: string): boolean {
  const s = normalizedStatus(status);
  if (isIssueStatus(status)) return false;
  if (NON_FINAL_DELIVERY_TERMS.some((term) => s.includes(term))) return false;
  return /\b(delivered|delivred|geliefert)\b/.test(s);
}

export function getStatusColor(status: string): string {
  const s = normalizedStatus(status);
  if (isDeliveredStatus(status)) return "text-cyber-green";
  if (s.includes("auth") || s.includes("required") || s.includes("not found")) return "text-cyber-yellow";
  if (isIssueStatus(status)) return "text-cyber-red";
  if (s.includes("transit")) return "text-cyber-cyan";
  if (s.includes("custom")) return "text-cyber-yellow";
  if (s.includes("out for delivery")) return "text-cyber-purple";
  if (s.includes("pending") || s.includes("label")) return "text-cyber-muted";
  return "text-cyber-text";
}

export function getStatusBadgeClass(status: string): string {
  const s = normalizedStatus(status);
  if (isDeliveredStatus(status)) return "cyber-badge-success";
  if (isIssueStatus(status) && !(s.includes("auth") || s.includes("required") || s.includes("not found"))) {
    return "cyber-badge-danger";
  }
  if (s.includes("auth") || s.includes("required") || s.includes("not found")) return "cyber-badge-warning";
  if (s.includes("custom")) return "cyber-badge-warning";
  if (s.includes("transit") || s.includes("out for delivery")) return "cyber-badge-info";
  return "cyber-badge";
}
