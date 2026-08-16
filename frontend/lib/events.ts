/** Commands the browser publishes to the agent. Keep in step with
 *  CoPilot.handle_ui_command on the backend. */
export type UiCommand =
  | { command: "start_mock_interview"; job_id: number }
  /** Leaving the practice screen. Without this the browser goes home while the
   *  session stays an interviewer, and the next request comes back as another
   *  interview question. */
  | { command: "end_practice" };

export type JccEvent =
  | { type: "jobs.updated"; payload: { count: number } }
  | { type: "scores.updated"; payload: { count: number } }
  | { type: "application.moved"; payload: { job_id: number; stage: string } }
  | { type: "interview.scheduled"; payload: { job_id: number; when: string } }
  | { type: "mode.changed"; payload: { mode: string } }
  | { type: "navigate"; payload: { path: string } }
  | { type: "ui.command"; payload: UiCommand };

export function decode(data: Uint8Array): JccEvent | null {
  try {
    return JSON.parse(new TextDecoder().decode(data)) as JccEvent;
  } catch {
    return null;
  }
}

/** The agent publishes on this same channel, so its events echo back here —
 *  only "ui.command" travels browser to agent. */
export function encode(payload: UiCommand): Uint8Array<ArrayBuffer> {
  const bytes = new TextEncoder().encode(
    JSON.stringify({ type: "ui.command", payload }),
  );
  // TextEncoder's result is typed as possibly SharedArrayBuffer-backed, which
  // publishData rejects. Copy into a plain buffer rather than cast the type
  // away.
  return new Uint8Array(bytes);
}
