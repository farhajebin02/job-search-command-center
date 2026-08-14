export type JccEvent =
  | { type: "jobs.updated"; payload: { count: number } }
  | { type: "scores.updated"; payload: { count: number } }
  | { type: "application.moved"; payload: { job_id: number; stage: string } }
  | { type: "interview.scheduled"; payload: { job_id: number; when: string } }
  | { type: "mode.changed"; payload: { mode: string } }
  | { type: "navigate"; payload: { path: string } };

export function decode(data: Uint8Array): JccEvent | null {
  try {
    return JSON.parse(new TextDecoder().decode(data)) as JccEvent;
  } catch {
    return null;
  }
}
