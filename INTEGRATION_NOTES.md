> **SUPERSEDED (Phase 9).** This file was written before Phases 1-8 and several statements below are no longer true (e.g. memory-only profiles, `level: 0`, evidence-wording required/preferred, 12 tests, no fuzzy matching). Current truth: `README.md`, `docs/CONTRACT.md`, `docs/COMPLIANCE_MATRIX.md`, `docs/INTEGRATION_AUDIT.md`. Kept for history.

# Integration audit and fixes

## Contract alignment

The October 2026 participant brief defines five handoffs: JD Analytics → JD skill list; Resume Parsing → extracted skills/details; Profile Builder → saved profile; Talent Check → company readiness plus 12 category gaps; Skill Matching → job-specific match score and missing/matched skills. The app has five distinct workflows/endpoints in one React UI. One unified UI is acceptable; each module's contract and behavior must remain represented.

## Important fixes in this revision

- Corrected the 12-category order to match the original Role 4 `skill_set_master` IDs and its benchmark arrays: `COD, DSA, APTI, COMM, OOD, AI, SQL, SYSD, CLOUD, SWE, NETW, OS`. The previous combined draft had reordered OOD/APTI/COMM and SQL/CLOUD/SWE/SYSD, which could assign the wrong company's level to a category.
- Profile Builder now exposes manual edit fields for hackathons, internships, certifications, preferred roles, and projects, as required by the brief; it has Save and Load controls.
- Supabase persistence is implemented as an optional server-side adapter. JD analyses write to the existing `jd_analytics_results` table. Candidate profiles and Role 4/5 result records use the new optional migration under `supabase/migrations/`.
- Talent Check uses the three-company local snapshot in the Role 4 package, consistent with the brief's explicit instruction to use the supplied local snapshot for the three companies in scope. It does not silently swap to the broader 115-company table.
- Gemini/Groq/OpenRouter are backend-only providers for JD and resume extraction. If no provider is configured, keyword fallback is clearly labelled. Talent Check scoring and Skill Matching weights remain deterministic code.
- Numeric candidate proficiency is not inferred from keywords. A level must be explicitly entered in Profile Builder.

## Remaining external setup / limitations

- Apply `supabase/migrations/20261028_radix_persistence.sql` in the intended Supabase project to enable profile and result persistence. The original Role 1 migration for `jd_analytics_results` must already be applied as documented in the Role 1 package.
- Configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` only in `backend/.env`; never in frontend variables or a committed file. The service-role key bypasses RLS and must stay server-side.
- If Supabase is not configured, profile save/load is session-memory only. The API reports this in `storage_mode` and responses.
- Resume parsing and JD extraction have a labelled keyword fallback; full extraction requires a working LLM API key. Scanned PDFs need OCR and are not supported by the current text extraction path.
- The current skill matching implementation uses canonical aliases and exact normalized skill comparison; it does not use embeddings. The brief allows exact/fuzzy matching if time is limited, but semantic equivalence should not be claimed.
- Required/preferred classification from JD evidence is a first pass and must be reviewed against source text. The extractor's evidence-grounding checks are guardrails, not a guarantee.
- The supplied hackathon sample pack should be used for manual validation: at least two JDs and two resumes, and preferably all six JDs/four resumes before the demo.

## Current module status after this revision

1. **JD Analytics:** PDF/DOCX extraction, structured shared skill contract, required/preferred lists, LLM adapter and labelled fallback; optional persistence to `jd_analytics_results`.
2. **Resume Parsing:** PDF/DOCX extraction, structured skills and profile details, evidence/confidence, and profile pre-fill; LLM adapter and labelled fallback.
3. **Profile Builder:** manual edit of basic details, skills/evidence/explicit levels, hackathons, internships, certifications, preferred roles and projects; Save/Load endpoint; durable Supabase storage after migration.
4. **Talent Check:** all 12 skillsets, local three-company snapshot, transparent normalized readiness formula and gap list. Category order is aligned to Role 4 source.
5. **Skill Matching:** specific JD's required/preferred skills, 2:1 weighted match score, matched/missing lists and recommendations; optional persistence.

## Test status

The included backend test suite checks endpoints, aliases, missing-level behavior, save/load, Profile Builder fields and benchmark category ordering. This does not replace a live Supabase smoke test or manual validation against the official sample documents.
