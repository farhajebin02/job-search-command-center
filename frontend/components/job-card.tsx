"use client";

import { motion } from "framer-motion";
import {
  useConnectionState,
  useLocalParticipant,
  useVoiceAssistant,
} from "@livekit/components-react";
import { ConnectionState } from "livekit-client";
import { AlertTriangle, Check, ExternalLink, MessagesSquare } from "lucide-react";
import { useState } from "react";
import { markApplied, setStage } from "@/lib/api";
import { encode } from "@/lib/events";
import { STAGES, STAGE_LABEL, type Job, type Stage } from "@/lib/types";

const STAGE_TONE: Record<Stage, string> = {
  saved: "border-neutral-600 bg-neutral-800 text-neutral-200",
  applied: "border-sky-800 bg-sky-950 text-sky-300",
  screening: "border-violet-800 bg-violet-950 text-violet-300",
  round_1: "border-violet-800 bg-violet-950 text-violet-300",
  round_2: "border-violet-800 bg-violet-950 text-violet-300",
  final: "border-amber-800 bg-amber-950 text-amber-300",
  offer: "border-emerald-800 bg-emerald-950 text-emerald-300",
  rejected: "border-red-900 bg-red-950 text-red-400",
};

const UNTRACKED_TONE = "border-neutral-800 bg-neutral-900 text-neutral-500";

export function JobCard({ job }: { job: Job }) {
  const m = job.match;
  const serverStage = job.stage ?? null;
  const [stage, setStageValue] = useState<Stage | null>(serverStage);
  const [lastServerStage, setLastServerStage] = useState<Stage | null>(serverStage);

  // useState only reads its argument on first mount, so the local value used to
  // shadow the prop for the life of the card. A stage changed by voice reached
  // the server and the pipeline rail — which renders straight from props — but
  // never the card. Adopt the server's value whenever it actually changes,
  // which still leaves optimistic updates visible in between refreshes.
  if (serverStage !== lastServerStage) {
    setLastServerStage(serverStage);
    setStageValue(serverStage);
  }

  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const { localParticipant } = useLocalParticipant();
  const connection = useConnectionState();
  const { agent } = useVoiceAssistant();
  // publishData resolves happily into an empty room, so a connected room is not
  // enough — without an agent subscribed, the command goes nowhere and the
  // click looks broken with no error to show for it.
  const canPractice = connection === ConnectionState.Connected && agent !== undefined;

  const move = async (next: Stage) => {
    const previous = stage;
    setStageValue(next); // optimistic
    setPending(true);
    setError(null);
    try {
      await setStage(job.id, next);
      window.dispatchEvent(new Event("jcc:refresh"));
    } catch (e) {
      // Roll back rather than leave the card asserting a stage the server
      // never accepted.
      setStageValue(previous);
      setError(e instanceof Error ? e.message : "Could not update status");
    } finally {
      setPending(false);
    }
  };

  const apply = async () => {
    setPending(true);
    setError(null);
    try {
      await markApplied(job.id);
      setStageValue("applied");
      window.dispatchEvent(new Event("jcc:refresh"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not mark applied");
    } finally {
      setPending(false);
    }
  };

  const practice = async () => {
    setError(null);
    try {
      // Same command the voice path takes, so the agent swaps to the
      // interviewer persona instead of the co-pilot narrating an empty screen.
      await localParticipant.publishData(
        encode({ command: "start_mock_interview", job_id: job.id }),
        { reliable: true },
      );
    } catch {
      setError("Could not reach the assistant. Is the agent running?");
    }
  };

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

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {/* Native select: the status is legible at a glance and editable in the
            same control, with keyboard and screen-reader support for free. */}
        <label className="sr-only" htmlFor={`stage-${job.id}`}>
          Application status for {job.title} at {job.company}
        </label>
        <select
          id={`stage-${job.id}`}
          value={stage ?? ""}
          disabled={pending}
          onChange={(e) => move(e.target.value as Stage)}
          className={`rounded-md border px-2.5 py-1.5 text-sm font-medium disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400 ${
            stage ? STAGE_TONE[stage] : UNTRACKED_TONE
          }`}
        >
          <option value="" disabled>
            Not tracked
          </option>
          {STAGES.map((s) => (
            <option key={s} value={s} className="bg-neutral-900 text-neutral-100">
              {STAGE_LABEL[s]}
            </option>
          ))}
        </select>

        {!stage && (
          <button
            onClick={apply}
            disabled={pending}
            className="rounded-md border border-neutral-700 px-3 py-1.5 text-sm hover:bg-neutral-800 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400"
          >
            Mark applied
          </button>
        )}

        <button
          onClick={practice}
          disabled={!canPractice}
          title={
            canPractice
              ? undefined
              : "Waiting for the assistant to join — practice needs it running"
          }
          className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 px-3 py-1.5 text-sm hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400"
        >
          <MessagesSquare className="h-3.5 w-3.5" aria-hidden="true" />
          Practice
        </button>

        <a
          href={job.apply_url}
          target="_blank"
          rel="noopener noreferrer"
          className={`ml-auto inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400 ${
            stage === "applied"
              ? "animate-pulse bg-emerald-400 text-neutral-900 motion-reduce:animate-none"
              : "bg-neutral-100 text-neutral-900 hover:bg-white"
          }`}
        >
          Open <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </a>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-sm text-red-400">
          {error}
        </p>
      )}
    </motion.article>
  );
}
