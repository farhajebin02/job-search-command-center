"use client";

import { Upload } from "lucide-react";
import { useResumeUpload, type ResumeUploadHandlers } from "@/lib/use-resume-upload";

export function Dropzone({
  error,
  ...handlers
}: ResumeUploadHandlers & {
  /** Controlled error message to render (kept as a prop since this component
   *  remounts fresh each time the parent switches back to the "empty" state
   *  after a failed upload). */
  error?: string | null;
}) {
  const { upload } = useResumeUpload(handlers);

  return (
    <div className="grid h-full place-items-center">
      <label
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files[0]); }}
        className="flex w-full max-w-xl cursor-pointer flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-neutral-700 p-16 text-center hover:border-neutral-500 focus-within:border-neutral-500"
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
          onChange={(e) => upload(e.target.files?.[0])}
        />
      </label>
      {error && <p role="alert" className="mt-4 text-sm text-red-400">{error}</p>}
    </div>
  );
}
