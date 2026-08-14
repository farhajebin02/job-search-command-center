"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { JobCard } from "@/components/job-card";
import type { Job } from "@/lib/types";

function SearchContent() {
  const q = useSearchParams().get("q") ?? "";
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
    fetch(`${base}/api/search?q=${encodeURIComponent(q)}`)
      .then((r) => r.json())
      .then((d) => setJobs(d.jobs));
  }, [q]);

  // Unscored jobs sort last, not first — score descending, missing score treated as lowest.
  const sorted = [...jobs].sort((a, b) => (b.match?.score ?? -1) - (a.match?.score ?? -1));

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-sm uppercase tracking-wide text-neutral-500">
          “{q}” · {jobs.length}
        </h1>
        <Link href="/" className="text-sm text-neutral-400 hover:text-neutral-200">
          Back to feed
        </Link>
      </div>
      {jobs.length === 0 && <p className="text-neutral-600">Nothing matched.</p>}
      <div className="flex flex-col gap-3">
        {sorted.map((j) => <JobCard key={j.id} job={j} />)}
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div />}>
      <SearchContent />
    </Suspense>
  );
}
