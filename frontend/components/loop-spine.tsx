"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

const SEGMENTS = [
  // Discover and Score were separate segments pointing at the same route.
  // Scoring runs automatically after every fetch, so the two counts were always
  // equal and the split told the user nothing.
  { key: "discover", label: "Discover", href: "/" },
  { key: "apply", label: "Apply", href: "/pipeline?stage=applied" },
  // Track is the whole board, not one column of it. It used to point at the
  // interviewing stages alone, which is the one question it cannot answer:
  // where each company stands.
  { key: "track", label: "Track", href: "/pipeline?stage=all" },
  { key: "schedule", label: "Schedule", href: "/pipeline?stage=interviewing" },
  { key: "practice", label: "Practice", href: null },
] as const;

export function LoopSpine({ counts }: { counts: Record<string, number> }) {
  const pathname = usePathname();
  const stage = useSearchParams().get("stage");

  const matches = (href: string) =>
    href === "/" ? pathname === "/" : href.includes(stage ?? " ");

  // Multiple segments can map to the same route (e.g. Discover/Score both
  // land on "/"). Only the first matching segment should light up, so the
  // spine always shows exactly one active segment rather than a cluster.
  const activeKey = SEGMENTS.find((s) => s.href !== null && matches(s.href))?.key;

  return (
    <nav className="flex items-stretch gap-1 border-b border-neutral-800 px-4 py-2">
      {SEGMENTS.map((s) =>
        s.href === null ? (
          <span
            key={s.key}
            aria-disabled="true"
            className="flex-1 cursor-not-allowed rounded-md px-3 py-2 text-center text-xs text-neutral-600"
          >
            <span className="block">{s.label}</span>
            <span className="block font-mono tabular-nums text-sm text-neutral-700">
              {counts[s.key] ?? 0}
            </span>
          </span>
        ) : (
          <Link
            key={s.key}
            href={s.href}
            className={`flex-1 rounded-md px-3 py-2 text-center text-xs transition-colors ${
              s.key === activeKey
                ? "bg-neutral-800 text-neutral-100"
                : "text-neutral-500 hover:bg-neutral-900"
            }`}
          >
            <span className="block">{s.label}</span>
            <span className="block font-mono tabular-nums text-sm text-neutral-300">
              {counts[s.key] ?? 0}
            </span>
          </Link>
        ),
      )}
    </nav>
  );
}
