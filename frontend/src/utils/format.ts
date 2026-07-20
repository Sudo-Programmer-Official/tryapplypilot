import type { AlertEvent, JobOpportunity, SourceStatus, StatusTone } from "../types";

const notificationReasonLabels: Record<string, string> = {
  already_alerted: "Already alerted",
  below_match_threshold: "Below match threshold",
  collected: "Collected",
  connector_retry: "Recovery retry",
  daily_digest_scheduled: "Queued for daily digest",
  fresh_match: "Fresh alert candidate",
  freshness_expired: "Freshness window expired",
  initial_sync_stale: "Too old during first sync",
  initial_sync_suppressed: "Suppressed during first sync",
  notification_rule_filtered: "Filtered by notification rules",
  recovery_backfill_budget_exhausted: "Recovery budget exhausted",
  telegram_delivery_failed: "Telegram delivery failed",
  telegram_not_connected: "Telegram not connected",
  unknown: "Unknown reason",
};

const notificationTypeLabels: Record<string, string> = {
  fresh_alert: "Fresh Alerts",
  recovery_alert: "Recovery Alerts",
  daily_digest: "Daily Digest",
  unknown: "Unknown",
};

function humanizeLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function formatPercent(value: number, digits = 0): string {
  return `${value.toFixed(digits)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Unavailable";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unavailable";
  }
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Unavailable";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unavailable";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatDurationSeconds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Unavailable";
  }
  if (value < 60) {
    return `${Math.round(value)} sec`;
  }
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return seconds > 0 ? `${minutes} min ${seconds} sec` : `${minutes} min`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function getInitials(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0]?.toUpperCase() ?? "")
    .join("");
}

export function stringToHue(value: string): number {
  return Array.from(value).reduce((total, char) => total + char.charCodeAt(0), 0) % 360;
}

export function companyMarkStyle(value: string): Record<string, string> {
  const hue = stringToHue(value);
  return {
    background: `linear-gradient(135deg, hsla(${hue}, 88%, 54%, 0.16), hsla(${(hue + 36) % 360}, 88%, 54%, 0.3))`,
    color: `hsl(${hue}, 82%, 42%)`,
  };
}

export function formatRelativeMinutes(minutes: number): string {
  if (minutes <= 2) {
    return "Just now";
  }
  if (minutes < 60) {
    return `${minutes} min ago`;
  }
  if (minutes < 60 * 24) {
    return `${Math.round(minutes / 60)} hr ago`;
  }
  if (minutes < 60 * 48) {
    return "Yesterday";
  }
  return `${Math.round(minutes / (60 * 24))} days ago`;
}

export function sourceStatusTone(source: SourceStatus): StatusTone {
  if (!source.enabled) {
    return "inactive";
  }
  if (source.state === "healthy") {
    return "healthy";
  }
  if (source.state === "lagging") {
    return "warning";
  }
  return "failed";
}

export function systemStatusTone(status: string): StatusTone {
  if (status === "healthy") {
    return "healthy";
  }
  if (status === "lagging" || status === "warning") {
    return "warning";
  }
  if (status === "degraded" || status === "failed") {
    return "failed";
  }
  return "inactive";
}

export function alertAgeLabel(alert: AlertEvent): string {
  return formatRelativeMinutes(alert.sent_minutes_ago);
}

export function notificationReasonLabel(reason: string | null | undefined): string {
  if (!reason) {
    return "Unknown reason";
  }
  return notificationReasonLabels[reason] ?? humanizeLabel(reason);
}

export function notificationTypeLabel(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  return notificationTypeLabels[value] ?? humanizeLabel(value);
}

export function notificationStatusTone(status: string | null | undefined): "success" | "warning" | "danger" | "info" | "neutral" {
  if (status === "sent") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "suppressed") {
    return "warning";
  }
  if (status === "digest_pending" || status === "pending") {
    return "info";
  }
  return "neutral";
}

export function sortJobsByScore(jobs: JobOpportunity[]): JobOpportunity[] {
  return [...jobs].sort((left, right) => right.match_score - left.match_score || left.posted_minutes_ago - right.posted_minutes_ago);
}

export function buildLinePath(values: number[], width: number, height: number): string {
  if (values.length === 0) {
    return "";
  }
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = Math.max(max - min, 1);
  return values
    .map((value, index) => {
      const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function extractJobTrend(values: JobOpportunity[]): number[] {
  const buckets = Array.from({ length: 7 }, () => 0);
  values.forEach((job) => {
    const dayIndex = Math.min(6, Math.max(0, Math.floor(job.posted_minutes_ago / (60 * 24))));
    buckets[6 - dayIndex] += 1;
  });
  return buckets;
}
