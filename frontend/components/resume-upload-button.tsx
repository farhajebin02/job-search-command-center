"use client";

import { RefreshCw } from "lucide-react";
import { useResumeUpload, type ResumeUploadHandlers } from "@/lib/use-resume-upload";

/** Compact counterpart to the dropzone, for swapping the résumé once jobs are
 *  already on screen. */
export function ResumeUploadButton(props: ResumeUploadHandlers) {
  const { upload, uploading } = useResumeUpload(props);

  return (
    <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-800 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-neutral-400">
      <RefreshCw
        className={`h-3.5 w-3.5 ${uploading ? "animate-spin motion-reduce:animate-none" : ""}`}
        aria-hidden="true"
      />
      {uploading ? "Rescoring…" : "Replace résumé"}
      <input
        type="file"
        accept="application/pdf"
        className="sr-only"
        disabled={uploading}
        onChange={(e) => upload(e.target.files?.[0])}
      />
    </label>
  );
}
