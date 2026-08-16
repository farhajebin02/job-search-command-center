"use client";

import { useState } from "react";
import { uploadResume } from "./api";
import type { Job } from "./types";

export type ResumeUploadHandlers = {
  onUploaded: (jobs: Job[]) => void;
  /** Fires the instant a file is accepted, before the ~50s upload/score round
   *  trip resolves. */
  onUploadStart?: () => void;
  /** Fires if the upload rejects, so the caller can return the surface to a
   *  state the user can retry from. */
  onUploadError?: (message: string) => void;
};

/** Shared by the full dropzone and the compact replace button so the long
 *  upload-and-score round trip is handled the same way from either entry
 *  point. Uploading again simply supersedes the stored profile — the backend
 *  reads the most recent one. */
export function useResumeUpload({
  onUploaded,
  onUploadStart,
  onUploadError,
}: ResumeUploadHandlers) {
  const [uploading, setUploading] = useState(false);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    onUploadStart?.();
    try {
      const { jobs } = await uploadResume(file);
      onUploaded(jobs);
      window.dispatchEvent(new Event("jcc:refresh"));
    } catch (e) {
      onUploadError?.(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return { upload, uploading };
}
