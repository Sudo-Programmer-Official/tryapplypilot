import type { AuthUser, ResumeAsset } from "../types";
import { requestJson, requestMultipart } from "./client";

export function fetchUserResumes(): Promise<{ items: ResumeAsset[] }> {
  return requestJson<{ items: ResumeAsset[] }>("/api/auth/me/resumes");
}

export function uploadUserResume(file: File): Promise<{ item: ResumeAsset; user: AuthUser }> {
  const form = new FormData();
  form.append("file", file);
  return requestMultipart<{ item: ResumeAsset; user: AuthUser }>("/api/auth/me/resumes", form);
}
