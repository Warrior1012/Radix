# RADIX: Review of AI use in Modules 3–5

## Decision

The three modules now have distinct responsibilities for AI. Existing score calculation remains deterministic and auditable.

### Module 3 — Profile Builder
- Added an optional `POST /api/profile-review` read-only review.
- It reviews completeness and evidence quality and can recommend profile improvements.
- It does not edit, add, or save profile fields. Candidate skill labels returned by the model are validated against skills already in the profile.
- The request payload sent to an AI provider excludes name, email, candidate ID, and CV filename. Skills/evidence and profile content such as education, projects, experience, and certifications may be sent when the user clicks **AI profile review**.
- It uses the same configured Gemini/Groq/OpenRouter keys with sequential provider fallback.

Why not run another automatic rewriting pass? Resume Parsing already uses AI to extract the resume. A second automatic rewrite is redundant and could overwrite user corrections or invent data. A separate read-only review is safer and provides distinct value.

### Module 4 — Talent Check
- Added `POST /api/talent-coach` and a result card in Talent Check.
- The backend recomputes the benchmark result from the submitted profile/company before preparing the coaching prompt.
- AI provides strengths supported by the assessed data, concrete practice actions, evidence suggestions, and a suggested 7-day plan.
- No model-generated score is accepted. The numerical readiness score, category levels, and gaps are still produced by `compute_talent_check`.
- If no category has an explicit proficiency level, the LLM is skipped and the UI asks the candidate to assess at least one skill first.
- A provider outage/rate limit does not fail or replace the deterministic Talent Check result.

### Module 5 — Skill Matching
- Preserves exact, alias, phrase, and guarded fuzzy matching.
- Existing AI semantic assist only proposes mappings from a JD requirement to a skill label already present in the candidate profile and requires source evidence from both sides.
- The deterministic scorer revalidates suggestions and calculates all points. AI cannot invent a candidate skill or directly set the match score.

## Configuration

The new features use existing server-side provider keys; no new API keys are needed.

- `AI_PROFILE_REVIEW=true`
- `PROFILE_REVIEW_PROVIDER_ORDER=gemini,groq,openrouter`
- `AI_TALENT_COACHING=true`
- `TALENT_COACH_PROVIDER_ORDER=gemini,groq,openrouter`
- `AI_SEMANTIC_MATCHING=true`
- `SKILL_MATCH_PROVIDER_ORDER=groq,gemini,openrouter`

Set these in `backend/.env` if desired; the `.env.example` includes blank placeholders for provider keys. Never put provider keys in frontend env variables or a shared ZIP.

## Verification performed

- Backend test suite: **215 passed**.
- `python -m compileall -q app.py radix_jd tests`: passed.
- Babel parse: `App.jsx`, `ResultsPanel.jsx`, `ProfilePanel.jsx`, `ResumePanel.jsx`, and `api.js`: passed.
- PostCSS parse of `styles.css`: passed.
- Added offline tests for provider fallback, profile-review privacy filtering, no-level guard, category/skill output validation, and deterministic score preservation.

## Not verified here

- Real calls to Gemini, Groq, or OpenRouter were not made; availability, quotas, model compatibility and cost depend on the user's keys/provider accounts.
- Live Supabase access was not tested.
- Vite build/browser E2E could not be completed in this environment: the available node_modules copy lacked the Linux Rollup optional native package. This is an environment/dependency limitation, so build should be run on the user's machine after `npm ci`.
