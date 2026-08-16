"use client";

import {
  useVoiceAssistant,
  useLocalParticipant,
  useConnectionState,
  BarVisualizer,
} from "@livekit/components-react";
import { ConnectionState } from "livekit-client";
import { agentStatus, DOT_CLASS, type AgentTone } from "@/lib/agent-state";
import { AudioGate } from "./audio-gate";
import { ChatInput } from "./chat-input";
import { MicControl } from "./mic-control";
import { Transcript } from "./transcript";

export function VoiceRail() {
  const { state, audioTrack } = useVoiceAssistant();
  const { isMicrophoneEnabled } = useLocalParticipant();

  const connection = useConnectionState();
  const roomConnected = connection === ConnectionState.Connected;

  const status = agentStatus(state);
  // A muted mic makes "Listening" a lie — the agent is waiting on audio that
  // will never arrive. While it's speaking or working, its own state is still
  // the more useful thing to show.
  const showMuted =
    !isMicrophoneEnabled && (state === "listening" || state === "idle");

  // Room state outranks agent state: with no room there is no agent, and
  // "Offline" alone doesn't tell you which of the two is missing.
  const label = !roomConnected
    ? `Room ${connection}`
    : showMuted
      ? "Muted"
      : status.label;
  const tone: AgentTone = !roomConnected
    ? "offline"
    : showMuted
      ? "idle"
      : status.tone;

  return (
    <aside className="flex w-[280px] shrink-0 flex-col gap-4 border-r border-neutral-800 p-4">
      <div
        aria-live="polite"
        className="flex items-center gap-2 text-sm text-neutral-400"
      >
        <span
          aria-hidden="true"
          className={`h-2 w-2 shrink-0 rounded-full ${DOT_CLASS[tone]}`}
        />
        <span>{label}</span>
      </div>

      <div className="h-24 rounded-lg bg-neutral-900 p-2">
        <BarVisualizer state={state} barCount={7} trackRef={audioTrack} />
      </div>

      <AudioGate />

      <MicControl />

      {!roomConnected && (
        <p className="rounded-md bg-neutral-900 px-3 py-2 text-center text-xs text-red-400">
          Not connected to the room. Voice and chat are both unavailable until
          this clears.
        </p>
      )}

      {roomConnected && showMuted && (
        <p className="rounded-md bg-neutral-900 px-3 py-2 text-center text-xs text-amber-400">
          The assistant can&apos;t hear you until the mic is on — or just type below.
        </p>
      )}

      <Transcript />

      <ChatInput />
    </aside>
  );
}
