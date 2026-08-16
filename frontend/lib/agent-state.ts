import type { AgentState } from "@livekit/components-react";

/** How a given agent state should read to the user.
 *  - `busy`    the agent is working and the UI must say so
 *  - `live`    connected and mid-conversation
 *  - `idle`    connected, waiting on the user
 *  - `offline` cannot hear the user at all, whatever the mic is doing */
export type AgentTone = "busy" | "live" | "idle" | "offline";

export type AgentStatus = { label: string; tone: AgentTone };

/** The SDK reports nine states. The rail used to branch on two and collapse the
 *  rest into "Idle", so a thinking agent — and a dead one — both looked like
 *  they were simply waiting. Every state gets an honest label here. */
const STATUS: Record<AgentState, AgentStatus> = {
  disconnected: { label: "Offline", tone: "offline" },
  connecting: { label: "Connecting", tone: "offline" },
  "pre-connect-buffering": { label: "Connecting", tone: "offline" },
  failed: { label: "Agent unavailable", tone: "offline" },
  initializing: { label: "Starting", tone: "offline" },
  idle: { label: "Idle", tone: "idle" },
  listening: { label: "Listening", tone: "live" },
  thinking: { label: "Thinking", tone: "busy" },
  speaking: { label: "Speaking", tone: "live" },
};

const UNKNOWN: AgentStatus = { label: "Idle", tone: "idle" };

/** Falls back rather than throwing: a future SDK state should degrade to a dull
 *  label, not crash the rail. */
export const agentStatus = (state: AgentState): AgentStatus =>
  STATUS[state] ?? UNKNOWN;

export const DOT_CLASS: Record<AgentTone, string> = {
  busy: "bg-amber-400 animate-pulse motion-reduce:animate-none",
  live: "bg-emerald-400",
  idle: "bg-neutral-600",
  offline: "bg-red-500",
};
