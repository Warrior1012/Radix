import { canonicalKey, normalizeSkillList } from "./normalize";
import type { MatchConfig, MatchInput, MatchResult, Recommendation } from "./types";

export const DEFAULT_CONFIG: MatchConfig = { required_weight: 2, preferred_weight: 1 };

export const DISCLAIMER =
  "Skill-coverage estimate only. It is not a prediction of hiring success or a complete assessment of candidate quality.";

export function round2(n: number): number {
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

/** Pure matching function: no React, no browser state, no network. */
export function matchSkills(input: MatchInput, config: Partial<MatchConfig> = {}): MatchResult {
  const weights: MatchConfig = {
    required_weight: validWeight(config.required_weight, DEFAULT_CONFIG.required_weight),
    preferred_weight: validWeight(config.preferred_weight, DEFAULT_CONFIG.preferred_weight),
  };
  const job = input?.job;
  const required = normalizeSkillList(job?.required_skills);
  const requiredKeys = new Set(required.map(canonicalKey));
  // A skill listed as both required and preferred counts once, as required.
  const preferred = normalizeSkillList(job?.preferred_skills).filter((s) => !requiredKeys.has(canonicalKey(s)));
  const candidateKeys = new Set(normalizeSkillList(input?.candidate?.skills).map(canonicalKey));

  const has = (s: string) => candidateKeys.has(canonicalKey(s));
  const matchedReq = required.filter(has);
  const missingReq = required.filter((s) => !has(s));
  const matchedPref = preferred.filter(has);
  const missingPref = preferred.filter((s) => !has(s));

  const possible = required.length * weights.required_weight + preferred.length * weights.preferred_weight;
  const earned = matchedReq.length * weights.required_weight + matchedPref.length * weights.preferred_weight;

  const recommendations: Recommendation[] = [
    ...missingReq.map((skill) => ({
      priority: "high" as const,
      skill,
      category: "required" as const,
      message: `Build and demonstrate ${skill} — it is a required skill for this role.`,
    })),
    ...missingPref.map((skill) => ({
      priority: "medium" as const,
      skill,
      category: "preferred" as const,
      message: `Consider gaining ${skill} — it is listed as preferred and would strengthen the profile.`,
    })),
  ];

  const unable = possible === 0;
  const score = unable ? null : round2((earned / possible) * 100);

  return {
    module: "skill-matching",
    version: "1.0.0",
    job_id: job?.job_id ?? "",
    company_id: job?.company_id ?? null,
    candidate_id: input?.candidate?.candidate_id ?? null,
    status: unable ? "unable_to_calculate" : "scored",
    match_score: score,
    score_label: unable ? "Unable to calculate" : `${score!.toFixed(2)}%`,
    reason: unable ? "This job has no required or preferred skill requirements recorded, so a score would not be meaningful." : null,
    weights,
    points: { earned, possible },
    matched_required_skills: matchedReq,
    missing_required_skills: missingReq,
    matched_preferred_skills: matchedPref,
    missing_preferred_skills: missingPref,
    counts: {
      matched_required: matchedReq.length,
      missing_required: missingReq.length,
      matched_preferred: matchedPref.length,
      missing_preferred: missingPref.length,
    },
    recommendations,
    disclaimer: DISCLAIMER,
  };
}

function validWeight(w: unknown, fallback: number): number {
  return typeof w === "number" && Number.isFinite(w) && w > 0 ? w : fallback;
}
