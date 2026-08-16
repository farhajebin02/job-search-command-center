"use client";

import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { useVoiceAssistant } from "@livekit/components-react";
import { useEffect, useState } from "react";
import { JobCard } from "./job-card";
import { agentStatus } from "@/lib/agent-state";
import type { Job } from "@/lib/types";

const FADE = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2 },
};

/** How long the agent must stay busy before the surface admits it. Short
 *  conversational turns finish well inside this; the fetch-and-score tools,
 *  which run for the better part of a minute, do not. */
const BUSY_GRACE_MS = 1500;

/** True once the agent has been working long enough that silence would read as
 *  a frozen UI. */
function useSustainedAgentWork(): boolean {
  const { state } = useVoiceAssistant();
  const busy = agentStatus(state).tone === "busy";
  const [sustained, setSustained] = useState(false);
  const [lastBusy, setLastBusy] = useState(busy);

  // Reset during render rather than in an effect: every transition in or out of
  // busy starts the grace period over, and an effect doing this would cascade.
  if (busy !== lastBusy) {
    setLastBusy(busy);
    setSustained(false);
  }

  useEffect(() => {
    if (!busy) return;
    const t = setTimeout(() => setSustained(true), BUSY_GRACE_MS);
    return () => clearTimeout(t);
  }, [busy]);

  return busy && sustained;
}

export function WorkSurface({
  state, jobs, children,
}: {
  state: "empty" | "loading" | "loaded";
  jobs: Job[];
  children?: React.ReactNode;
}) {
  // Unscored jobs sort last, not first — score descending, missing score treated as lowest.
  const sorted = [...jobs].sort(
    (a, b) => (b.match?.score ?? -1) - (a.match?.score ?? -1),
  );
  const agentWorking = useSustainedAgentWork();

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative h-full">
        {/* Layered over the surface rather than replacing it: the agent works
            on voice turns too, and swapping the list for skeletons would rip
            away whatever the user is reading. */}
        {agentWorking && (
          <div
            role="status"
            aria-label="The assistant is working on your request"
            className="absolute inset-x-0 top-0 z-10 h-0.5 overflow-hidden rounded-full bg-neutral-800"
          >
            <div className="h-full w-1/3 animate-[jcc-slide_1.2s_ease-in-out_infinite] rounded-full bg-amber-400 motion-reduce:w-full motion-reduce:animate-none" />
          </div>
        )}
        <AnimatePresence mode="wait">
          {state === "empty" && (
            <motion.div key="empty" {...FADE} className="h-full">
              {children}
            </motion.div>
          )}

          {state === "loading" && (
            <motion.div
              key="loading"
              {...FADE}
              className="mx-auto flex max-w-2xl flex-col gap-3"
              role="status"
              aria-label="Fetching and scoring matching jobs"
            >
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-40 animate-pulse rounded-xl bg-neutral-900 motion-reduce:animate-none"
                />
              ))}
            </motion.div>
          )}

          {state === "loaded" && (
            <motion.div key="loaded" {...FADE} className="mx-auto flex max-w-2xl flex-col gap-3">
              {sorted.map((j) => <JobCard key={j.id} job={j} />)}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
