"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Check, ExternalLink } from "lucide-react";
import type { Job } from "@/lib/types";

export function JobCard({ job }: { job: Job }) {
  const m = job.match;
  return (
    <motion.article
      layoutId={`job-${job.id}`}
      className="rounded-xl border border-neutral-800 bg-neutral-900 p-4"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="truncate font-medium">{job.title}</h3>
          <p className="truncate text-sm text-neutral-500">
            {job.company} · {job.location}
          </p>
        </div>
        {m && (
          <div className="shrink-0 rounded-full border border-neutral-700 px-3 py-1 font-mono text-sm tabular-nums">
            {m.score}
          </div>
        )}
      </div>

      {m && (
        <>
          <p className="mt-3 text-sm text-neutral-400">{m.rationale}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {m.matched_skills.map((s) => (
              <span key={s} className="inline-flex items-center gap-1 rounded-md bg-emerald-950 px-2 py-0.5 text-xs text-emerald-300">
                <Check className="h-3 w-3" aria-hidden="true" />{s}
              </span>
            ))}
            {m.gaps.map((g) => (
              <span key={g} className="inline-flex items-center gap-1 rounded-md bg-amber-950 px-2 py-0.5 text-xs text-amber-300">
                <AlertTriangle className="h-3 w-3" aria-hidden="true" />{g}
              </span>
            ))}
          </div>
        </>
      )}

      <a
        href={job.apply_url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-neutral-100 px-3 py-1.5 text-sm font-medium text-neutral-900 hover:bg-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400"
      >
        Open <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
      </a>
    </motion.article>
  );
}
