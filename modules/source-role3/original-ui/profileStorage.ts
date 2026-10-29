// Temporary localStorage persistence. Swap these two functions for Supabase later;
// the form only depends on saveProfile / loadProfile.
import { emptyProfile, type CandidateProfile } from "./profile";

const STORAGE_KEY = "radix_candidate_profile";

export async function saveProfile(profile: CandidateProfile): Promise<void> {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
}

export async function loadProfile(): Promise<CandidateProfile | null> {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return { ...emptyProfile(), ...JSON.parse(raw) };
  } catch {
    return null;
  }
}
