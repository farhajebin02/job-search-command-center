"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { fetchApplications } from "@/lib/api";
import type { Application } from "@/lib/types";

const INTERVIEWING = ["screening", "round_1", "round_2", "final"];

function PipelineContent() {
  const stage = useSearchParams().get("stage") ?? "applied";
  const [apps, setApps] = useState<Application[]>([]);

  useEffect(() => {
    const load = () => fetchApplications().then(({ applications }) => {
      setApps(applications.filter((a) =>
        stage === "interviewing" ? INTERVIEWING.includes(a.stage) : a.stage === stage));
    });
    load();
    window.addEventListener("jcc:refresh", load);
    return () => window.removeEventListener("jcc:refresh", load);
  }, [stage]);

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-sm uppercase tracking-wide text-neutral-500">
        {stage.replace("_", " ")} · {apps.length}
      </h1>
      {apps.length === 0 && <p className="text-neutral-600">Nothing at this stage yet.</p>}
      <ul className="flex flex-col gap-2">
        {apps.map((a) => (
          <li key={a.id} className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <div className="font-medium">{a.title}</div>
            <div className="text-sm text-neutral-500">{a.company}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function PipelinePage() {
  return (
    <Suspense fallback={<div />}>
      <PipelineContent />
    </Suspense>
  );
}
