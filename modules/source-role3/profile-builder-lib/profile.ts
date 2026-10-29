// Candidate profile types, defaults, and validation (Role 3).
import { z } from "zod";

export const CATEGORY_CODES = [
  "COD", "DSA", "OOD", "APTI", "COMM", "AI", "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS", "OTHER",
] as const;
export type CategoryCode = (typeof CATEGORY_CODES)[number];

export const CONFIDENCE_LEVELS = ["high", "medium", "low"] as const;
export type Confidence = (typeof CONFIDENCE_LEVELS)[number];

export interface Skill {
  skill_name: string;
  category_code: CategoryCode;
  evidence: string;
  confidence: Confidence;
}

export interface CandidateProfile {
  name: string;
  email: string;
  education: string;
  skills: Skill[];
  hackathons: string[];
  internships: string[];
  certifications: string[];
  preferred_roles: string[];
  cv_file: string; // selected filename only
}

export const emptySkill = (): Skill => ({
  skill_name: "",
  category_code: "COD",
  evidence: "",
  confidence: "medium",
});

export const emptyProfile = (): CandidateProfile => ({
  name: "",
  email: "",
  education: "",
  skills: [],
  hackathons: [],
  internships: [],
  certifications: [],
  preferred_roles: [],
  cv_file: "",
});

export const ACCEPTED_CV_EXTENSIONS = [".pdf", ".docx"];

export function isAcceptedCv(filename: string): boolean {
  const lower = filename.toLowerCase();
  return ACCEPTED_CV_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

const basicsSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(100, "Name must be under 100 characters"),
  email: z.string().trim().email("Enter a valid email").max(255, "Email must be under 255 characters"),
});

export function validateProfile(p: CandidateProfile): { name?: string | undefined; email?: string | undefined } {
  const r = basicsSchema.safeParse(p);
  if (r.success) return {};
  const errors: { name?: string | undefined; email?: string | undefined } = {};
  for (const issue of r.error.issues) {
    const key = issue.path[0] as "name" | "email";
    if (!errors[key]) errors[key] = issue.message;
  }
  return errors;
}
