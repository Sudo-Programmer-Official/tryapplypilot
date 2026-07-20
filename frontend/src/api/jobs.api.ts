import type { JobListResponse } from "../types";
import { requestJson } from "./client";

export function fetchAdminJobs(params: {
  minScore?: number;
  company?: string;
  status?: string;
  maxAgeHours?: number;
  query?: string;
  decision?: "APPLY_NOW" | "REVIEW" | "IGNORE" | "all";
  sortBy?: "highest_match" | "newest" | "company" | "recently_updated";
  limit?: number;
  offset?: number;
} = {}): Promise<JobListResponse> {
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
  if (params.query?.trim()) {
    search.set("query", params.query.trim());
  }
  if (params.decision && params.decision !== "all") {
    search.set("decision", params.decision);
  }
  if (params.sortBy) {
    search.set("sort_by", params.sortBy);
  }
  if (params.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  if (params.offset !== undefined) {
    search.set("offset", String(params.offset));
  }
  const query = search.size ? `?${search.toString()}` : "";
  return requestJson<JobListResponse>(`/api/jobs${query}`);
}
