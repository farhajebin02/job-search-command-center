"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

const SEGMENTS = [
  { key: "discover", label: "Discover", href: "/" },
  { key: "score", label: "Score", href: "/" },
  { key: "apply", label: "Apply", href: "/pipeline?stage=applied" },
  { key: "track", label: "Track", href: "/pipeline?stage=interviewing" },
  { key: "schedule", label: "Schedule", href: "/pipeline?stage=interviewing" },
  { key: "practice", label: "Practice", href: "/" },
] as const;

export function LoopSpine({ counts }: { counts: Record<string, number> }) {
  const pathname = usePathname();
  const stage = useSearchParams().get("stage");

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : href.includes(stage ?? " ");

  return (
    <nav className="flex items-stretch gap-1 border-b border-neutral-800 px-4 py-2">
      {SEGMENTS.map((s) => (
        <Link
          key={s.key}
          href={s.href}
          className={`flex-1 rounded-md px-3 py-2 text-center text-xs transition-colors ${
            isActive(s.href)
              ? "bg-neutral-800 text-neutral-100"
              : "text-neutral-500 hover:bg-neutral-900"
          }`}
        >
          <span className="block">{s.label}</span>
          <span className="block font-mono tabular-nums text-sm text-neutral-300">
            {counts[s.key] ?? 0}
          </span>
        </Link>
      ))}
    </nav>
  );
}
