"use client";

import { useVoiceAssistant, BarVisualizer } from "@livekit/components-react";
import { Mic } from "lucide-react";

export function VoiceRail() {
  const { state, audioTrack } = useVoiceAssistant();

  return (
    <aside className="flex w-[280px] shrink-0 flex-col gap-4 border-r border-neutral-800 p-4">
      <div className="flex items-center gap-2 text-sm text-neutral-400">
        <Mic className="h-4 w-4" aria-hidden="true" />
        <span>{state === "speaking" ? "Speaking" : state === "listening" ? "Listening" : "Idle"}</span>
      </div>
      <div className="h-24 rounded-lg bg-neutral-900 p-2">
        <BarVisualizer state={state} barCount={7} trackRef={audioTrack} />
      </div>
      <div
        aria-live="polite"
        className="flex-1 overflow-y-auto rounded-lg bg-neutral-900 p-3 text-sm leading-relaxed text-neutral-300"
      >
        <p className="text-neutral-500">Transcript appears here.</p>
      </div>
    </aside>
  );
}
