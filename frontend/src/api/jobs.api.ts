import type { JobOpportunity } from "../types";
import { requestJson } from "./client";

export function fetchAdminJobs(params: {
  minScore?: number;
  company?: string;
  status?: string;
  maxAgeHours?: number;
} = {}): Promise<{ items: JobOpportunity[] }> {
  const search = new URLSearchParams();
  if (params.minScore !== undefined) {
    search.set("min_score", String(params.minScore));
  }
  if (params.company) {
    search.set("company", params.company);
  }
  if (params.status) {
    search.set("status", params.status);
  }
  if (params.maxAgeHours !== undefined) {
    search.set("max_age_hours", String(params.maxAgeHours));
  }
  const query = search.size ? `?${search.toString()}` : "";
  return requestJson<{ items: JobOpportunity[] }>(`/api/jobs${query}`);
}
