# RADIX Talent Match

One integrated tool for the RADIX Talent Match hackathon: a candidate uploads a JD and a resume, builds a profile, and sees (a) how they stack up against a company's bar across the 12 RADIX skillsets and (b) how well they match one specific job posting, with the gap list first.

Stack: Python / FastAPI backend, React + Vite frontend, server-side Gemini/Groq/OpenRouter providers with fallback, and optional Supabase (local JSON files otherwise). The frontend uses a neo-brutalist ink/bone/chartreuse/oxblood design system with five separate role dashboards, a dedicated Flow Control wizard, Evidence & Eval, and About & Privacy. Motion is CSS/vector-based and respects reduced-motion preferences.

| Role | What it does | Code |
|---|---|---|
| 1 JD Analytics | PDF/DOCX -> required vs preferred skills (LLM) | `backend/radix_jd/extractor.py`, `requirement_type.py`, `jd_store.py` |
| 2 Resume Parsing | PDF/DOCX -> grounded skills + education, projects, experience, ... (LLM) | `backend/radix_jd/resume.py` |
| 3 Profile Builder | validated merge/save/load + optional read-only AI quality review | `backend/radix_jd/profiles.py`, `backend/radix_jd/profile_review.py` |
| 4 Talent Check | deterministic readiness score + AI advisory rating out of 10 + learning recommendations | `backend/radix_jd/talent_check.py`, `backend/radix_jd/talent_coach.py` |
| 5 Skill Matching | deterministic weighted score + optional evidence-grounded AI semantic assist | `backend/radix_jd/skill_match.py`, `backend/radix_jd/semantic_match.py` |

Shared contract and formulas: [`docs/CONTRACT.md`](docs/CONTRACT.md). Setup: [`INTEGRATION_SETUP.md`](INTEGRATION_SETUP.md). Requirement-by-requirement check: [`docs/COMPLIANCE_MATRIX.md`](docs/COMPLIANCE_MATRIX.md). What was and was not actually run: [`docs/INTEGRATION_AUDIT.md`](docs/INTEGRATION_AUDIT.md). Demo script: [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md).

## Frontend navigation

- **Overview**: connection state, stage rail and workflow launch.
- **Flow Control**: a single-screen view of the five-stage pipeline; run the full flow after selecting the JD and resume in their dashboards.
- **Five module dashboards**: JD Analytics, Resume Parsing, Profile Builder, Talent Check and Skill Matching.
- **Decision Lab**: requirement-level ProofGraph states (level entered, evidence available, claimed, unassessed) plus a hypothetical skill-demonstration simulator. It is read-only and does not persist assumptions.
- **Evidence & Eval**: measured evaluation artifact, real JD stats, saved-profile completeness and candidate-by-company readiness matrix. Missing data is shown as unavailable, not as fabricated zeroes.
- **About & Privacy**: score interpretation, AI/data handling, storage, limitations and terms of use.

The UI uses square panels, high-contrast flat color, animated vector pipeline graphics and controlled CSS transitions. It does not use a decorative gradient hero or fake evaluation metrics.

## Behaviour you should know about (it is intentional)

- **No silent fallbacks.** With `DEMO_FALLBACK=false` (default) a missing key or failed model call returns an error that names the cause (`rate_limited`, `auth`, `bad_json`, ...). With `DEMO_FALLBACK=true` a keyword fallback is used and the response is labelled `demo_keyword_fallback`; that is not AI.
- **Resume parsing never invents proficiency.** Skills come back with no `level`. `level` is `null` (blank in the UI, "not assessed") until a person enters 1-10. `0` is not a valid level.
- **Evidence is grounded.** A resume skill whose name or evidence quote is not found in the resume text is dropped and counted in `extraction_notes.dropped_skills_unsupported`.
- **Talent Check does not treat "not assessed" as "cannot do it".** The readiness score is the mean over *assessed* categories; `readiness_floor` (unassessed = 0) and `score_range` are always shown; fewer than 6 of 12 assessed is marked provisional. Nothing assessed gives `readiness_score: null`. The optional AI coach produces a separate advisory readiness rating out of 10, evidence-grounded learning actions, and a seven-day plan. The AI rating is constrained to within 1.5 points of the deterministic readiness score divided by 10, and confidence is forced low when fewer than 4 of 12 categories are assessed. It never changes this score.
- **Profile Builder AI review is read-only.** It can review profile completeness and evidence quality, but it never rewrites fields or sets proficiency levels. Name, email, candidate ID, and CV filename are excluded from the review prompt.
- **Skill Match remains explainable.** Required skills weigh 2, preferred 1. Exact, alias, phrase and guarded fuzzy matches are handled first. Optional AI semantic assist may suggest high-confidence equivalences only from supplied JD and resume evidence; candidate/JD labels are validated and the deterministic scorer still assigns all points. `exact_only_score`, `gaps[]`, `points_lost` and `why` remain available.
- **Decision Lab is additive and stateless.** Its ProofGraph distinguishes explicit levels, evidence text, unsubstantiated claims, and requirements not found in the current profile. The What-if Simulator applies the existing deterministic 2:1 required/preferred weighting to hypothetical skill demonstrations in memory only; it never changes or saves a profile. See [Decision Lab documentation](docs/DECISION_LAB.md).
- **Benchmark** = the official three-company snapshot `backend/data/talent_check_company_skillsets.json`. Live Supabase companies, if any, are a separately labelled extra (`supabase:` ids).
- **Storage.** Supabase when `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are set; otherwise local JSON files in `backend/data/profiles/` and `backend/data/jds/` (git-ignored). `/api/health` reports `storage_mode: supabase | local-file`.
- Scores estimate skill coverage; they are not hiring probabilities.

## Run locally (Windows PowerShell)

Requires Python 3.11+ and Node.js 20+.

```powershell
# 1. backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env      # then edit backend\.env (see below)
cd backend
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# 2. frontend (second terminal, from the project root)
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. API docs: <http://127.0.0.1:8000/docs>. `START_BACKEND.bat` / `START_FRONTEND.bat` do the same steps.

### Configure `backend\.env` (never commit it, never paste keys in chat)

| Variable | Meaning |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio key. Used as one configured provider for extraction/review/coaching. |
| `GEMINI_MODELS` | Model name(s). The example value is `gemini-3.1-flash-lite`; **confirm that name is valid for your key** - a wrong name shows up as `model_not_found`. |
| `GROQ_API_KEY`, `GROQ_MODELS` | Optional secondary provider and model list. |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODELS` | Optional fallback provider and model list. Free models can be rate-limited. |
| `RESUME_PROVIDER_ORDER`, `RESUME_MAX_PROVIDER_ATTEMPTS` | Controls resume parsing fallback order and attempts. |
| `AI_PROFILE_REVIEW`, `PROFILE_REVIEW_PROVIDER_ORDER` | Enables the optional read-only Profile Builder review and configures fallback order. |
| `AI_TALENT_COACHING`, `TALENT_COACH_PROVIDER_ORDER` | Enables evidence-grounded coaching; does not change benchmark scores. |
| `AI_SEMANTIC_MATCHING`, `SKILL_MATCH_PROVIDER_ORDER` | Enables evidence-grounded semantic skill suggestions; deterministic scoring remains authoritative. |
| `DEMO_FALLBACK` | `false` (default). `true` = labelled keyword fallback, offline demo only. |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Optional. Backend-only key; never in `frontend/.env`. |
| `CORS_ORIGINS`, `MAX_UPLOAD_MB` | Defaults are fine for local use. |
| `PROFILE_STORE_DIR`, `JD_STORE_DIR` | Optional overrides for the local file stores. |

### Optional: Supabase

In the Supabase SQL Editor run, in order: `supabase/migrations/20261027_create_jd_analytics_results.sql`, `20261028_radix_persistence.sql`, `20261029_radix_persistence_fixes.sql` (all additive; they do not touch your company tables). Restart the backend, then open `/api/integrations/status`: it should show Gemini configured, `supabase.connected: true` and `persistence_ready: true`. Details: `INTEGRATION_SETUP.md`.

### Live smoke test (do this once on your machine - it has never been run live)

1. `GET /api/health` -> `llm_configured: true`, `demo_fallback: false`.
2. Upload a JD: `analysis_meta.processing_path` must not be `demo_keyword_fallback`, and the result must contain both required and preferred skills.
3. Upload a resume: check `extraction_notes.dropped_skills_unsupported` is not eating real skills.
4. Enter a few levels, save, restart the backend, load the same `candidate_id` (proves persistence).
5. Run Talent Check for each company and Skill Match against the analysed JD (`jd_id`). Repeat with a second, different candidate: the numbers must differ.

## Tests

```powershell
cd backend
pip install -r requirements-dev.txt
pytest -q                      # backend unit/integration tests

cd ..\frontend
$env:RADIX_TEST_API='http://127.0.0.1:8000'   # backend running with DEMO_FALLBACK=true and no keys
npm test                       # jsdom UI flow test; skipped when RADIX_TEST_API is unset
npm run build
```

Latest offline backend run for this reviewed source: **227 passed**. Tests use synthetic fixtures/mocked providers and fake Supabase; they do not verify live provider accounts, the live database, or a real-browser build.

## Evidence and evaluation (official samples required)

The frontend's **Evidence & Eval** page displays only values derived from a saved evaluation artifact, a real JD analysis, saved profile records, or a calculated readiness matrix. It does not seed precision/recall values or example candidate scores.

The evaluation harness is in `backend/eval/`: `dataset/manifest.json` names the ten official logical inputs (six JDs and four resumes); each row needs both `pdf_path` and `docx_path`. `ground_truth/annotations.json` is deliberately empty. Team members must manually annotate each original document and a second team member must review it before setting `approved: true`. Run the backend, configure the paths relative to the project root, and run `python eval/run_eval.py --api-base http://127.0.0.1:8000` from `backend/`. A subset report is labelled `partial`; until every official item has approved labels and both formats are scored, a final benchmark is not claimed. See `backend/eval/README.md`.

The harness measures extraction precision/recall/F1, matched requirement-type accuracy where comparable labels exist, latency/model calls, and PDF/DOCX skill-set overlap. It does not claim to be a full robustness benchmark until official documents and the team's agreed scenarios are exercised.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status, providers, `storage_mode`, `demo_fallback` |
| GET | `/api/integrations/status` | AI + Supabase configuration and table probes (no secrets) |
| GET | `/api/companies` | the 3 snapshot companies (+ labelled Supabase ones) |
| POST | `/api/analyze-jd` | multipart `file`, optional `company`, `role` -> skills, `jd_id`, `analysis_meta` |
| POST | `/api/parse-resume` | multipart `file` -> profile draft |
| POST | `/api/profile` | validated save (422 on invalid) |
| GET | `/api/profile/{candidate_id}` | load |
| GET | `/api/profiles` | saved candidate summaries + computed completeness |
| DELETE | `/api/profile/{candidate_id}` | delete a saved profile |
| POST | `/api/profile/merge-resume` | `{profile, parsed}` -> merged profile + report (stateless; client saves) |
| POST | `/api/profile-review` | `profile` -> optional read-only AI review of profile completeness/evidence |
| GET | `/api/jd/stats/{jd_id}` | category, requirement, confidence counts + recorded latency/cache/model-call metadata |
| POST | `/api/talent-check` | `{profile, company_id}` -> deterministic readiness + 12 category rows |
| POST | `/api/talent-coach` | `{profile, company_id}` -> AI rating (0–10) and coaching based on a server-recomputed Talent Check; rating is validated and bounded against deterministic score; no score from AI is accepted as official benchmark score |
| POST | `/api/analytics/matrix` | saved `candidate_ids` × `company_ids` -> readiness comparison |
| GET | `/api/eval/latest` | latest measured evaluation artifact, or unavailable/blocked status |
| POST | `/api/skill-match` | `{profile, jd_id}` or `{profile, job}` -> score + `gaps[]` |
| POST | `/api/decision-lab/proofgraph` | `{profile, job}` or `{profile, jd_id}` -> requirement-level evidence states (stateless) |
| POST | `/api/decision-lab/simulate` | `{profile, job, assumed_skills}` -> baseline vs hypothetical score; no persistence |

## Known limits

- The official six JDs and four resumes are not included in this source pack. The participant brief names Ananya Rao, Karthik Subramaniam, Priya Menon and Rohan Verma; the expected cross-candidate behaviour has not been checked against those official files.
- Text PDFs with varied column layout use PyMuPDF sorted text extraction when installed; DOCX paragraphs and tables are extracted. Scanned / image-only PDFs are still not supported (no OCR or direct PDF-to-model path).
- No authentication; the service-role key bypasses RLS, so run the backend only on a trusted machine.
- The original TypeScript Role 1/3/5 sources in `modules/` are reference snapshots only; their own test suites were not run here.
- The UI has not been exercised in a real browser by the build process.
