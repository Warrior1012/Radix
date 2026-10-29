> **SUPERSEDED (Phase 9).** This file was written before Phases 1-8 and several statements below are no longer true (e.g. memory-only profiles, `level: 0`, evidence-wording required/preferred, 12 tests, no fuzzy matching). Current truth: `README.md`, `docs/CONTRACT.md`, `docs/COMPLIANCE_MATRIX.md`, `docs/INTEGRATION_AUDIT.md`. Kept for history.

# RADIX Talent Match — requirements audit

Audit basis: `RADIX_Talent_Match_Hackathon_Brief.pdf` (October 2026), the supplied Role 1 JD Analytics package, Role 3 Profile Builder package, Role 4 Talent Check package, Role 5 SkillMatch Studio package, and the previously combined ZIP. Role 2 was present in the combined backend as a resume-parsing implementation; no separate Role 2 ZIP was included among the source archives available for this audit.

## Official brief requirements vs this build

| Role | Required by brief | Status in this revision | Remaining validation |
|---|---|---|---|
| 1 — JD Analytics | Upload PDF/DOCX; extract skills mapped to 12 categories plus named technologies; hand off structured skill list | Implemented with shared skill contract, LLM extraction, grounded evidence checks, required/preferred lists and optional `jd_analytics_results` persistence | Manually validate required/preferred classification and evidence against the six official JDs; live provider + Supabase test pending |
| 2 — Resume Parsing | Upload PDF/DOCX; extract skills plus reliable education, projects and experience; hand off to Profile Builder | Implemented with separate endpoint and LLM extraction; keyword fallback is labelled; output pre-fills editable profile | Manually validate all four official resumes; scanned/image-only PDF OCR is not supported |
| 3 — Profile Builder | Basic details, skills, hackathons, internships, certifications, preferred roles, CV upload; save/load JSON | Implemented in unified React UI with manual fields, skills/evidence/confidence/explicit level, projects and experience; save/load API; optional Supabase persistence | Live save/reload test after applying migration; no authentication/authorization layer for multi-user production use |
| 4 — Talent Check | Saved profile + selected company; readiness score and gaps across all 12 categories; local snapshot for three companies | Implemented using `backend/data/talent_check_company_skillsets.json`; all 12 categories returned, levels explicitly entered, transparent normalized scoring | Confirm snapshot values with the team/facilitator; validate score behavior with the official sample candidates |
| 5 — Skill Matching | One candidate profile/resume + one JD skill list; match score and matched/missing skills | Implemented with required weight 2, preferred weight 1, original Role 5 canonical alias approach, matched/missing lists and recommendations | Run original Role 5 test suite in its own Node environment; validate against official sample JD/resume combinations |

## Defects found and corrected

1. **Talent Check category-order bug:** the previous combined build used a different order than Role 4's skill IDs. This could apply the right numeric level to the wrong category (e.g., Aptitude vs OOD, SQL vs Cloud). The current category order matches the Role 4 snapshot: `COD, DSA, APTI, COMM, OOD, AI, SQL, SYSD, CLOUD, SWE, NETW, OS`.
2. **Benchmark format:** the brief explicitly names `talent_check_company_skillsets.json`. The current build loads the three-company snapshot from that JSON file and validates all 12 categories and 1–10 required levels at startup.
3. **Profile Builder completeness:** the previous combined UI omitted manual fields for hackathons, internships, certifications, preferred roles and projects, and did not expose Load. These fields and Load were added; resume experience is kept separate from internships.
4. **Persistence truthfulness:** the prior build used in-memory profiles only. This revision adds an optional server-side Supabase REST adapter and a migration for candidate profiles and Talent Check/Skill Matching result JSON. API responses report whether storage is Supabase or demo-memory.
5. **Skill normalization:** expanded the alias map to cover the supplied Role 5 aliases (e.g. JavaScript/JS, AWS/Amazon Web Services, React/React.js, PostgreSQL/Postgres, C++/CPP, Kubernetes/K8s) and corrected a substring-category bug that could classify “Tailwind” as AI.

## Persistence instructions

- The original Role 1 migration is included at `supabase/migrations/20261027_create_jd_analytics_results.sql`.
- The new migration is `supabase/migrations/20261028_radix_persistence.sql`.
- Apply the migrations in the intended Supabase project before expecting durable writes. The app does not run migrations automatically and does not alter the existing company/skill benchmark tables.
- Configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `backend/.env` only. Never put the service-role key in React env variables or commit it.
- The brief directs Talent Check to use the local three-company snapshot. The wider company tables in Supabase are not silently substituted for that specified snapshot.

## Tests executed in this environment

- Combined backend suite: **12 passed**. Covers health/company list, skill matching, no inferred proficiency, profile save/load and profile fields, category ordering, JD upload contract, resume upload contract, and a profile → Talent Check / Skill Matching end-to-end path.
- Original Role 1 tests: **22 passed**.
- Original Role 4 tests: **3 passed**.
- Frontend production build: **not verified** because `npm install` timed out in this environment before dependencies were installed. Run `npm install` then `npm run build` on the demo machine.
- Live Gemini and Supabase smoke tests: **not run** because no credentials were provided. Never paste those secrets into chat.

## Demo-readiness checklist

- [ ] Set Gemini (or another supported provider) API key in backend `.env` and check `/api/health`.
- [ ] Apply both SQL migrations in the correct Supabase project and verify `storage_mode: supabase`.
- [ ] Upload at least two official JDs and two official resumes; review extracted evidence and required/preferred classification.
- [ ] Save a profile, refresh/restart backend, and load it again to prove durable persistence.
- [ ] Run Talent Check and Skill Matching for at least two deliberately different candidate profiles; confirm results visibly differ.
- [ ] Run `npm install`, `npm run build`, and `pytest -q` on the machine used for presentation.
- [ ] Rehearse the entire flow without developer tools or manual API calls.


## Integration configuration improvements (2026-10-28)

- Added `GET /api/integrations/status`, a read-only diagnostic that reports configured AI providers and probes the existing Supabase company schema plus RADIX persistence tables. It never returns keys.
- Added an integration status strip to the UI so the demo visibly distinguishes AI configured, Supabase connected, missing migrations, and missing credentials.
- Changed the example configuration to `DEMO_FALLBACK=false` and made Resume Parsing fail visibly if AI extraction fails while fallback is disabled; keyword-only results can no longer silently masquerade as AI.
- Reduced per-table Supabase diagnostic probe timeout to 3 seconds.
- Live Gemini/Supabase connectivity still requires the user's own credentials and SQL migrations; those cannot be verified from this environment.

- Extended the Supabase adapter to read `companies`, `skill_set_master`, and `company_skill_levels` without schema mutation. Complete database-backed 12-category benchmarks are exposed alongside (not instead of) the three official snapshot companies.
- Added test coverage for selecting a Supabase-backed company and calculating Talent Check from its live required levels.
- Gemini is now the first provider target when configured, so the Resume Parsing module uses Gemini first.
