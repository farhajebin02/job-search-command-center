"use client";

import { Upload } from "lucide-react";
import { uploadResume } from "@/lib/api";
import type { Job } from "@/lib/types";

export function Dropzone({
  onUploaded,
  onUploadStart,
  onUploadError,
  error,
}: {
  onUploaded: (jobs: Job[]) => void;
  /** Fires the instant a file is accepted, before the ~50s upload/score round trip resolves. */
  onUploadStart?: () => void;
  /** Fires if the upload rejects, so the caller can return the surface to "empty" for retry. */
  onUploadError?: (message: string) => void;
  /** Controlled error message to render (kept as a prop since this component remounts fresh
   *  each time the parent switches back to the "empty" state after a failed upload). */
  error?: string | null;
}) {
  const handle = async (file: File | undefined) => {
    if (!file) return;
    onUploadStart?.();
    try {
      const { jobs } = await uploadResume(file);
      onUploaded(jobs);
      window.dispatchEvent(new Event("jcc:refresh"));
    } catch (e) {
      onUploadError?.(e instanceof Error ? e.message : "Upload failed");
    }
  };

  return (
    <div className="grid h-full place-items-center">
      <label
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handle(e.dataTransfer.files[0]); }}
        className="flex w-full max-w-xl cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-neutral-700 p-16 text-center hover:border-neutral-500"
      >
        <Upload className="h-8 w-8 text-neutral-500" aria-hidden="true" />
        <span className="text-lg font-medium">Drop your resume</span>
        <span className="text-sm text-neutral-500">
          PDF. Matching jobs are fetched and scored automatically.
        </span>
        <input
          type="file"
          accept="application/pdf"
          className="sr-only"
          onChange={(e) => handle(e.target.files?.[0])}
        />
      </label>
      {error && <p role="alert" className="mt-4 text-sm text-red-400">{error}</p>}
    </div>
  );
}
