"use client";

import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { JobCard } from "./job-card";
import type { Job } from "@/lib/types";

const FADE = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2 },
};

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

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative h-full">
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
