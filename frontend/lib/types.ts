export type Match = {
  score: number;
  matched_skills: string[];
  gaps: string[];
  rationale: string;
};

/** Mirrors core.tracker.STAGES. Order is the pipeline progression, so it also
 *  drives the grouping in the pipeline rail. */
export const STAGES = [
  "saved", "applied", "screening", "round_1",
  "round_2", "final", "offer", "rejected",
] as const;

export type Stage = (typeof STAGES)[number];

export const STAGE_LABEL: Record<Stage, string> = {
  saved: "Saved",
  applied: "Applied",
  screening: "Screening",
  round_1: "Round 1",
  round_2: "Round 2",
  final: "Final",
  offer: "Offer",
  rejected: "Rejected",
};

export type Job = {
  id: number;
  title: string;
  company: string;
  location: string;
  description: string;
  apply_url: string;
  salary_min: number | null;
  salary_max: number | null;
  match: Match | null;
  /** Absent or null until the job is tracked. */
  stage?: Stage | null;
};

export type Application = {
  id: number;
  job_id: number;
  stage: Stage;
  title: string;
  company: string;
  apply_url: string;
  updated_at: string;
};
