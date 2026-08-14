"use client";

import { useVoiceAssistant, BarVisualizer } from "@livekit/components-react";
import Link from "next/link";
import { use } from "react";

export default function PracticePage({
  params,
}: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const { state, audioTrack } = useVoiceAssistant();

  return (
    <main className="grid h-dvh place-items-center bg-neutral-950 p-8">
      <div className="flex w-full max-w-xl flex-col items-center gap-6">
        <p className="text-sm uppercase tracking-widest text-neutral-500">
          Mock interview · job {jobId}
        </p>
        <div className="h-40 w-full rounded-2xl bg-neutral-900 p-4">
          <BarVisualizer state={state} barCount={9} trackRef={audioTrack} />
        </div>
        <p aria-live="polite" className="text-neutral-400">
          {state === "speaking" ? "Interviewer is speaking" : "Your turn"}
        </p>
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-300">
          Exit interview
        </Link>
      </div>
    </main>
  );
}
