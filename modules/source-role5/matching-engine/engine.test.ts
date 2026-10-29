import { describe, expect, it } from "vitest";
import { matchSkills } from "./engine";
import { canonicalKey, extractSkillsFromText, parseSkillText } from "./normalize";

const job = (required: string[], preferred: string[] = []) => ({
  job_id: "j1",
  company_id: "c1",
  required_skills: required,
  preferred_skills: preferred,
});

describe("matching engine", () => {
  it("weights required 2 and preferred 1, rounded to 2 decimals", () => {
    // possible = 3*2 + 1 = 7 ; earned = 1*2 + 0 = 2 -> 28.57
    const r = matchSkills({ job: job(["Python", "SQL", "AWS"], ["Docker"]), candidate: { candidate_id: null, skills: ["python"] } });
    expect(r.points).toEqual({ earned: 2, possible: 7 });
    expect(r.match_score).toBe(28.57);
  });

  it("preferred only match earns 1 point", () => {
    const r = matchSkills({ job: job(["Python"], ["Docker"]), candidate: { candidate_id: null, skills: ["Docker"] } });
    expect(r.match_score).toBe(33.33);
  });

  it("recognizes aliases JS/JavaScript, TS/TypeScript, Postgres/PostgreSQL", () => {
    const r = matchSkills({
      job: job(["JavaScript", "TypeScript", "PostgreSQL"]),
      candidate: { candidate_id: null, skills: ["js", "TS", "postgres"] },
    });
    expect(r.match_score).toBe(100);
  });

  it("returns Unable to calculate when job has no requirements", () => {
    const r = matchSkills({ job: job([]), candidate: { candidate_id: null, skills: ["Python"] } });
    expect(r.status).toBe("unable_to_calculate");
    expect(r.match_score).toBeNull();
    expect(r.score_label).toBe("Unable to calculate");
  });

  it("does not substring match (Java vs JavaScript)", () => {
    const r = matchSkills({ job: job(["Java"]), candidate: { candidate_id: null, skills: ["JavaScript"] } });
    expect(r.match_score).toBe(0);
    expect(canonicalKey("Java")).not.toBe(canonicalKey("JavaScript"));
  });

  it("dedupes candidate skills and lists required gaps first in recommendations", () => {
    const r = matchSkills({ job: job(["Python", "SQL"], ["Docker"]), candidate: { candidate_id: null, skills: ["Python", "python", " PYTHON "] } });
    expect(r.points.earned).toBe(2);
    expect(r.recommendations.map((x) => x.skill)).toEqual(["SQL", "Docker"]);
  });

  it("parses comma batch input and extracts whole-word skills from text", () => {
    expect(parseSkillText("React, js ,react;Docker")).toEqual(["React", "JavaScript", "Docker"]);
    expect(extractSkillsFromText("Worked at Google using JavaScript and Postgres", ["Java"])).toEqual(["JavaScript", "PostgreSQL"]);
  });
});
