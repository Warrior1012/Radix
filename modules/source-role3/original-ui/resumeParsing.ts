// Hook for Role 2 (resume parser). No endpoint is defined yet.
// When Role 2 is ready, set RESUME_PARSER_CONNECTED = true and implement the call below.
import type { CandidateProfile } from "./profile";

export const RESUME_PARSER_CONNECTED = false;

export type ParseResult =
  | { ok: true; profile: Partial<CandidateProfile> }
  | { ok: false; message: string };

export async function requestResumeParsing(_file: File): Promise<ParseResult> {
  if (!RESUME_PARSER_CONNECTED) {
    return { ok: false, message: "Resume parsing (Role 2) is not connected yet." };
  }
  // TODO(Role 2): send _file to the Role 2 parser and map its response to Partial<CandidateProfile>.
  return { ok: false, message: "Resume parsing (Role 2) is not implemented yet." };
}
