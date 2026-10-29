// Integration contract for the Skill Matching module. JSON-serializable only.

export type Identifier = string | number;

export interface MatchJobInput {
  job_id: Identifier;
  company_id: Identifier | null;
  required_skills: string[];
  preferred_skills: string[];
}

export interface MatchCandidateInput {
  candidate_id: Identifier | null;
  skills: string[];
}

export interface MatchInput {
  job: MatchJobInput;
  candidate: MatchCandidateInput;
}

export interface MatchConfig {
  required_weight: number;
  preferred_weight: number;
}

export interface Recommendation {
  priority: "high" | "medium";
  skill: string;
  category: "required" | "preferred";
  message: string;
}

export interface MatchResult {
  module: "skill-matching";
  version: "1.0.0";
  job_id: Identifier;
  company_id: Identifier | null;
  candidate_id: Identifier | null;
  status: "scored" | "unable_to_calculate";
  /** null when status is unable_to_calculate */
  match_score: number | null;
  score_label: string;
  reason: string | null;
  weights: MatchConfig;
  points: { earned: number; possible: number };
  matched_required_skills: string[];
  missing_required_skills: string[];
  matched_preferred_skills: string[];
  missing_preferred_skills: string[];
  counts: {
    matched_required: number;
    missing_required: number;
    matched_preferred: number;
    missing_preferred: number;
  };
  recommendations: Recommendation[];
  disclaimer: string;
}
