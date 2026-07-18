import type { SourceStatus } from "../types";
import { requestJson } from "./client";

export function fetchConnectorSources(): Promise<{ items: SourceStatus[] }> {
  return requestJson<{ items: SourceStatus[] }>("/api/sources");
}
