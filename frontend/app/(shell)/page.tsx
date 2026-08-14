"use client";

import { useEffect, useState } from "react";
import { Dropzone } from "@/components/dropzone";
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

  return (
    <WorkSurface state={state} jobs={jobs}>
      <Dropzone
        error={uploadError}
        onUploadStart={() => {
          // Flip to the skeleton state the instant a file is accepted — the upload/score
          // round trip measures ~50s and must never look like a frozen dropzone.
          setUploadError(null);
          setState("loading");
        }}
        onUploaded={(j) => {
          setJobs(j);
          setState("loaded");
        }}
        onUploadError={(message) => {
          // Return to "empty" so the dropzone (and retry) is reachable again, instead of
          // stranding the user on skeletons forever.
          setUploadError(message);
          setState("empty");
        }}
      />
    </WorkSurface>
  );
}
