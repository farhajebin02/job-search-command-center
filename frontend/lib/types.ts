export type Match = {
  score: number;
  matched_skills: string[];
  gaps: string[];
  rationale: string;
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
};

export type Application = {
  id: number;
  job_id: number;
  stage: string;
  title: string;
  company: string;
  apply_url: string;
  updated_at: string;
};
