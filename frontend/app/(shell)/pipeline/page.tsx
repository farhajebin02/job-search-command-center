"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { fetchApplications } from "@/lib/api";
import { STAGES, STAGE_LABEL, type Application, type Stage } from "@/lib/types";

const INTERVIEWING: Stage[] = ["screening", "round_1", "round_2", "final"];

/** Views that span more than one stage. These get grouped headings, because
 *  the question they answer is "where does each company stand" — a flat list
 *  cannot answer it. */
const TITLES: Record<string, string> = {
  all: "Every application",
  interviewing: "Interviewing",
};

function keep(stage: string, a: Application): boolean {
  if (stage === "all") return true;
  if (stage === "interviewing") return INTERVIEWING.includes(a.stage);
  return a.stage === stage;
}

function ApplicationList({ items }: { items: Application[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {items.map((a) => (
        <li key={a.id} className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
          <div className="font-medium">{a.title}</div>
          <div className="text-sm text-neutral-500">{a.company}</div>
        </li>
      ))}
    </ul>
  );
}

function PipelineContent() {
  const stage = useSearchParams().get("stage") ?? "applied";
  const [apps, setApps] = useState<Application[]>([]);

  useEffect(() => {
    const load = () => fetchApplications().then(({ applications }) => {
      setApps(applications.filter((a) => keep(stage, a)));
    });
    load();
    window.addEventListener("jcc:refresh", load);
    return () => window.removeEventListener("jcc:refresh", load);
  }, [stage]);

  const grouped = stage in TITLES;
  // STAGES order is the pipeline progression, so grouping by it reads top to
  // bottom the way the search itself moves.
  const groups = STAGES.map((s) => ({
    stage: s,
    items: apps.filter((a) => a.stage === s),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-sm uppercase tracking-wide text-neutral-500">
        {TITLES[stage] ?? stage.replace("_", " ")} · {apps.length}
      </h1>
      {apps.length === 0 && <p className="text-neutral-600">Nothing at this stage yet.</p>}

      {grouped ? (
        <div className="flex flex-col gap-6">
          {groups.map((g) => (
            <section key={g.stage}>
              <h2 className="mb-2 flex items-baseline gap-2 text-xs uppercase tracking-wide text-neutral-500">
                {STAGE_LABEL[g.stage]}
                <span className="font-mono tabular-nums text-neutral-600">
                  {g.items.length}
                </span>
              </h2>
              <ApplicationList items={g.items} />
            </section>
          ))}
        </div>
      ) : (
        <ApplicationList items={apps} />
      )}
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
