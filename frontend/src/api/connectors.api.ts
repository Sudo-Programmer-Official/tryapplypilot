import type {
  AdminConnectorsWorkspace,
  CompanyPreference,
  ConnectorCompanyErrorRecord,
  ConnectorCompanyJobRecord,
  MaintenanceStatusSnapshot,
  RunHistoryItem,
  SourceStatus,
} from "../types";
import { requestJson } from "./client";

export function fetchConnectorSources(): Promise<{ items: SourceStatus[] }> {
  return requestJson<{ items: SourceStatus[] }>("/api/sources");
}

export function fetchAdminConnectorsWorkspace(): Promise<AdminConnectorsWorkspace> {
  return requestJson<AdminConnectorsWorkspace>("/api/admin/connectors/workspace");
}

export function runConnectorNow(connectorKey: string): Promise<RunHistoryItem | { runs: unknown[] }> {
  return requestJson<RunHistoryItem | { runs: unknown[] }>(`/api/admin/connectors/${connectorKey}/run-now`, {
    method: "POST",
  });
}

export function validateConnectorCompany(companyId: string): Promise<{ item: Record<string, unknown> }> {
  return requestJson<{ item: Record<string, unknown> }>(`/api/admin/connectors/companies/${companyId}/validate`, {
    method: "POST",
  });
}

export function setConnectorCompanyMonitoring(companyId: string, enabled: boolean): Promise<{ item: CompanyPreference }> {
  return requestJson<{ item: CompanyPreference }>(`/api/admin/connectors/companies/${companyId}/monitoring`, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

export function fetchConnectorCompanyJobs(companyId: string): Promise<{ items: ConnectorCompanyJobRecord[] }> {
  return requestJson<{ items: ConnectorCompanyJobRecord[] }>(`/api/admin/connectors/companies/${companyId}/jobs`);
}

export function fetchConnectorCompanyErrors(companyId: string): Promise<{ items: ConnectorCompanyErrorRecord[] }> {
  return requestJson<{ items: ConnectorCompanyErrorRecord[] }>(`/api/admin/connectors/companies/${companyId}/errors`);
}

export function fetchMaintenanceStatus(): Promise<MaintenanceStatusSnapshot> {
  return requestJson<MaintenanceStatusSnapshot>("/api/admin/maintenance/status");
}

export function runMaintenanceNow(): Promise<MaintenanceStatusSnapshot> {
  return requestJson<MaintenanceStatusSnapshot>("/api/admin/maintenance/run-now", {
    method: "POST",
  });
}
