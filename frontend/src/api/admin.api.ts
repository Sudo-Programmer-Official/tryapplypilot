import type { AlertEvent, AuditLogEntry, CompanyRequest, DashboardSnapshot } from "../types";
import { requestJson } from "./client";

export function fetchDashboard(): Promise<DashboardSnapshot> {
  return requestJson<DashboardSnapshot>("/api/dashboard");
}

export function fetchAdminCompanyRequests(): Promise<{ items: CompanyRequest[] }> {
  return requestJson<{ items: CompanyRequest[] }>("/api/catalog/company-requests");
}

export function reviewCompanyRequest(
  requestId: string,
  payload: {
    status: "approved" | "rejected";
    admin_notes: string;
    connector: string;
    external_identifier: string;
    career_url: string;
    tier: number;
    priority: number;
    poll_interval_minutes: number;
    country: string;
    enabled: boolean;
    role_families: string[];
  },
): Promise<{ item: CompanyRequest }> {
  return requestJson<{ item: CompanyRequest }>(`/api/catalog/company-requests/${requestId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function fetchAdminAlerts(): Promise<{ items: AlertEvent[] }> {
  return requestJson<{ items: AlertEvent[] }>("/api/alerts");
}

export function fetchAuditLogs(): Promise<{ items: AuditLogEntry[] }> {
  return requestJson<{ items: AuditLogEntry[] }>("/api/audit-logs");
}
