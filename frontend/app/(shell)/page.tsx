"use client";

import { useEffect, useState } from "react";
import { Dropzone } from "@/components/dropzone";
import { ResumeUploadButton } from "@/components/resume-upload-button";
import { WorkSurface } from "@/components/work-surface";
import { fetchJobs } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function FeedPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [state, setState] = useState<"empty" | "loading" | "loaded">("loading");
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      fetchJobs()
        .then(({ jobs }) => {
          setJobs(jobs);
          setState(jobs.length ? "loaded" : "empty");
        })
        .catch((e) => {
          // Backend unreachable / network blip: land on the dropzone instead of
          // stranding the user on a skeleton that will never resolve.
          console.error("fetchJobs failed", e);
          setUploadError(e instanceof Error ? e.message : "Could not load jobs");
          setState("empty");
        });
    load();
    window.addEventListener("jcc:refresh", load);
    return () => window.removeEventListener("jcc:refresh", load);
  }, []);

  // Flip to the skeleton state the instant a file is accepted — the upload/score
  // round trip measures ~50s and must never look like a frozen surface.
  const onUploadStart = () => {
    setUploadError(null);
    setState("loading");
  };
  const onUploaded = (j: Job[]) => {
    setJobs(j);
    setState(j.length ? "loaded" : "empty");
  };
  // Return to a state the user can retry from, instead of stranding them on
  // skeletons forever.
  const onUploadError = (message: string) => {
    setUploadError(message);
    setState(jobs.length ? "loaded" : "empty");
  };

  return (
    <div className="flex h-full flex-col gap-3">
      {state === "loaded" && (
        <div className="mx-auto flex w-full max-w-2xl items-center justify-end">
          <ResumeUploadButton
            onUploadStart={onUploadStart}
            onUploaded={onUploaded}
            onUploadError={onUploadError}
          />
        </div>
      )}
      {state === "loaded" && uploadError && (
        <p role="alert" className="mx-auto w-full max-w-2xl text-sm text-red-400">
          {uploadError}
        </p>
      )}
      <div className="min-h-0 flex-1">
        <WorkSurface state={state} jobs={jobs}>
          <Dropzone
            error={uploadError}
            onUploadStart={onUploadStart}
            onUploaded={onUploaded}
            onUploadError={onUploadError}
          />
        </WorkSurface>
      </div>
    </div>
  );
}
