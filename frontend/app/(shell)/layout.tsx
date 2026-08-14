"use client";

import { Suspense, useEffect, useState } from "react";
import { VoiceRail } from "@/components/voice-rail";
import { LoopSpine } from "@/components/loop-spine";
import { PipelineRail } from "@/components/pipeline-rail";
import { fetchApplications, fetchJobs } from "@/lib/api";
import type { Application } from "@/lib/types";

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  const [apps, setApps] = useState<Application[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    const load = async () => {
      const [{ applications }, { jobs }] = await Promise.all([
        fetchApplications(), fetchJobs(),
      ]);
      setApps(applications);
      setCounts({
        discover: jobs.length,
        score: jobs.filter((j) => j.match).length,
        apply: applications.filter((a) => a.stage !== "saved").length,
        track: applications.filter((a) =>
          ["screening", "round_1", "round_2", "final"].includes(a.stage)).length,
        schedule: 0,
        practice: 0,
      });
    };
    load();
    window.addEventListener("jcc:refresh", load);
    return () => window.removeEventListener("jcc:refresh", load);
  }, []);

  return (
    <div className="flex h-dvh flex-col">
      <Suspense fallback={<div className="h-14 border-b border-neutral-800" />}>
        <LoopSpine counts={counts} />
      </Suspense>
      <div className="flex min-h-0 flex-1">
        <VoiceRail />
        <main className="min-w-0 flex-1 overflow-y-auto p-6">{children}</main>
        <PipelineRail applications={apps} />
      </div>
    </div>
  );
}
