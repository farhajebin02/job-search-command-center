"use client";

import {
  useVoiceAssistant,
  useLocalParticipant,
  BarVisualizer,
} from "@livekit/components-react";
import { useRouter } from "next/navigation";
import { use } from "react";
import { encode } from "@/lib/events";
import { AudioGate } from "@/components/audio-gate";
import { ChatInput } from "@/components/chat-input";
import { MicControl } from "@/components/mic-control";
import { Transcript } from "@/components/transcript";
import { agentStatus, DOT_CLASS } from "@/lib/agent-state";

export default function PracticePage({
  params,
}: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const { state, audioTrack } = useVoiceAssistant();
  const { localParticipant } = useLocalParticipant();
  const router = useRouter();
  const status = agentStatus(state);

  // "Your turn" was shown for every state that wasn't speaking, so a thinking
  // interviewer looked like it was waiting on the candidate.
  const line =
    state === "speaking"
      ? "Interviewer is speaking"
      : state === "thinking"
        ? "Interviewer is thinking"
        : state === "listening"
          ? "Your turn"
          : status.label;

  return (
    <main className="grid h-dvh place-items-center bg-neutral-950 p-8">
      <div className="flex w-full max-w-xl flex-col items-center gap-6">
        <p className="text-sm uppercase tracking-widest text-neutral-500">
          Mock interview · job {jobId}
        </p>
        <div className="h-40 w-full rounded-2xl bg-neutral-900 p-4">
          <BarVisualizer state={state} barCount={9} trackRef={audioTrack} />
        </div>
        <p
          aria-live="polite"
          className="flex items-center gap-2 text-neutral-400"
        >
          <span
            aria-hidden="true"
            className={`h-2 w-2 shrink-0 rounded-full ${DOT_CLASS[status.tone]}`}
          />
          {line}
        </p>
        <AudioGate />
        <MicControl autoOpen />
        <Transcript agentLabel="Interviewer" className="h-56 w-full" />
        <div className="w-full">
          <ChatInput />
        </div>
        <button
          type="button"
          onClick={async () => {
            // Tell the agent before leaving. Navigating alone left the session
            // as an interviewer, which then answered every later request with
            // another interview question.
            try {
              await localParticipant.publishData(
                encode({ command: "end_practice" }), { reliable: true });
            } catch {
              // Leaving matters more than the notification landing.
            }
            router.push("/");
          }}
          className="text-sm text-neutral-500 hover:text-neutral-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400"
        >
          Exit interview
        </button>
      </div>
    </main>
  );
}
