"use client";

import { STAGES, STAGE_LABEL, type Application } from "@/lib/types";

export function PipelineRail({ applications }: { applications: Application[] }) {
  const grouped = STAGES.map((stage) => ({
    stage,
    items: applications.filter((a) => a.stage === stage),
  })).filter((g) => g.items.length > 0);

  return (
    <aside className="w-[320px] shrink-0 overflow-y-auto border-l border-neutral-800 p-4">
      <h2 className="mb-3 text-sm font-medium text-neutral-400">Pipeline</h2>
      {grouped.length === 0 && (
        <p className="text-sm text-neutral-600">Nothing tracked yet.</p>
      )}
      {grouped.map((g) => (
        <details key={g.stage} open={g.stage === "applied"} className="mb-2">
          <summary className="cursor-pointer text-xs uppercase tracking-wide text-neutral-500">
            {STAGE_LABEL[g.stage]} ({g.items.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {g.items.map((a) => (
              <li key={a.id} className="rounded-md bg-neutral-900 px-3 py-2 text-sm">
                <div className="truncate font-medium">{a.title}</div>
                <div className="truncate text-xs text-neutral-500">{a.company}</div>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </aside>
  );
}
