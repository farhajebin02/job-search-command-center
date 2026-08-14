import type { Application, Job } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} failed: ${r.status}`);
  return r.json();
}

export const fetchJobs = () => get<{ jobs: Job[] }>("/api/jobs");
export const fetchApplications = () =>
  get<{ applications: Application[] }>("/api/applications");
export const fetchToken = (identity: string) =>
  get<{ token: string; url: string; room: string }>(
    `/api/token?identity=${encodeURIComponent(identity)}`,
  );

export async function uploadResume(file: File) {
  const body = new FormData();
  body.append("file", file);
  const r = await fetch(`${BASE}/api/upload`, { method: "POST", body });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Upload failed");
  return r.json() as Promise<{ jobs: Job[] }>;
}

export async function markApplied(jobId: number): Promise<void> {
  const r = await fetch(`${BASE}/api/applications/${jobId}/apply`, { method: "POST" });
  if (!r.ok) throw new Error(`Failed to mark job ${jobId} applied: ${r.status}`);
}
