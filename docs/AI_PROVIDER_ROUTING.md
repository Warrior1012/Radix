# RADIX AI Provider Routing and Module Responsibilities

## Which modules use AI?

- **JD Analytics:** Multi-provider LLM extraction and consensus. Extracted skill names are checked against source JD evidence.
- **Resume Parsing:** LLM extraction with provider fallback. It tries one model from each configured provider in `RESUME_PROVIDER_ORDER`. A model response must have a usable shape and verifiable skill evidence before it is accepted.
- **Profile Builder:** Not a separate LLM stage. It receives extracted resume data, merges it with the existing profile while preserving user edits, and leaves proficiency levels unassessed until a person sets them.
- **Talent Check:** Deterministic formula against a company benchmark. Only skills with a valid 1–10 proficiency level contribute; blank levels remain unassessed. AI must not invent these levels.
- **Skill Matching:** Deterministic weighted scoring (required=2 points, preferred=1) using exact names, aliases, a small explicit phrase map, and guarded fuzzy spelling. If unmatched JD skill labels remain, optional AI semantic assist may suggest high-confidence equivalences only when both original JD evidence and candidate skill evidence are available. Candidate/JD labels are validated against the supplied lists. The final score is still calculated by the deterministic scorer. If AI is unavailable or fails validation, the deterministic result is returned.

## Configuration

Create `backend/.env` from `backend/.env.example`, then fill the provider keys locally. Never add keys to frontend `.env` variables or commit `backend/.env`.

- `GEMINI_API_KEY`: Gemini provider key.
- `GROQ_API_KEY`: Groq provider key.
- `OPENROUTER_API_KEY`: OpenRouter provider key.
- `RESUME_PROVIDER_ORDER`: fallback order for resume parsing; defaults to `gemini,groq,openrouter`.
- `RESUME_MAX_PROVIDER_ATTEMPTS`: maximum providers to try; clamped to 1–3.
- `AI_PROFILE_REVIEW=true`: enable the optional read-only Profile Builder quality review.
- `PROFILE_REVIEW_PROVIDER_ORDER`: profile-review provider order; default `gemini,groq,openrouter`.
- `AI_TALENT_COACHING=true`: enable advisory Talent Check learning recommendations.
- `TALENT_COACH_PROVIDER_ORDER`: readiness-coach provider order; default `gemini,groq,openrouter`.
- `AI_SEMANTIC_MATCHING=true`: enable evidence-grounded AI semantic suggestions in Skill Matching.
- `SKILL_MATCH_PROVIDER_ORDER`: semantic-match provider order; default `groq,gemini,openrouter`.
- `DEMO_FALLBACK=false`: if every provider fails, return a clear API error instead of silently passing off keyword extraction as AI. Set `true` only for a demo; fallback responses are explicitly labeled non-AI.

The default OpenRouter model setting in `.env.example` is `openrouter/free`, which routes to an available free model. Free models can be rate-limited; keep Groq/Gemini enabled as alternate providers if available.

## Test commands

From `backend/`:

```powershell
python -m pytest -q
```

From `frontend/`:

```powershell
npm ci
npm run build
npm test
```

This package's offline Python regression suite is expected to run without real API keys. It does not make live provider or Supabase calls.


## Talent Check coaching

- `AI_TALENT_COACHING=true` enables supplementary, evidence-grounded recommendations after Talent Check.
- `TALENT_COACH_PROVIDER_ORDER=gemini,groq,openrouter` sets the provider fallback order for coaching.
- The AI coaching route recomputes the deterministic company benchmark result from the submitted profile and never accepts a model-generated score. It only returns learning actions and evidence suggestions. If no category has an explicit level, it skips the LLM and asks for an assessment first. Provider failure does not invalidate the Talent Check score.
- Profile Builder does not make an extra LLM call: it already receives AI-extracted resume fields from Resume Parsing, and a second generative rewrite could duplicate or overwrite candidate data.

## Profile Builder AI review

- `AI_PROFILE_REVIEW=true` enables an optional read-only profile quality review. `PROFILE_REVIEW_PROVIDER_ORDER=gemini,groq,openrouter` sets fallback order.
- The review sends curated profile skills/evidence and project/education text to the configured provider, excluding name, email, candidate ID, and CV filename. It returns suggestions only; it does not rewrite or save the profile. Only skill labels that already exist in the profile can be returned as skill reviews.
- This is separate from Resume Parsing: the parser extracts the resume, while this optional review checks completeness and evidence quality before the user saves/uses the profile.
