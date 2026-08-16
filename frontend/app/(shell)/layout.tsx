"use client";

import { Suspense, useEffect, useState } from "react";
import { VoiceRail } from "@/components/voice-rail";
import { LoopSpine } from "@/components/loop-spine";
import { PipelineRail } from "@/components/pipeline-rail";
import { EventBridge } from "@/components/event-bridge";
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
        // Each count has to be the number of rows its own page shows. Apply
        // counted everything past "saved" while the page it links to listed
        // only "applied", so the spine said 11 above a list of 6.
        apply: applications.filter((a) => a.stage === "applied").length,
        track: applications.length,
        schedule: applications.filter((a) =>
          ["screening", "round_1", "round_2", "final"].includes(a.stage)).length,
        practice: 0,
      });
    };
    const handleRefresh = () => load().catch(console.error);
    handleRefresh();
    window.addEventListener("jcc:refresh", handleRefresh);
    return () => window.removeEventListener("jcc:refresh", handleRefresh);
  }, []);

  return (
    <div className="flex h-dvh flex-col">
      <EventBridge />
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
