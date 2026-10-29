# Integration audit - real results only

Every number below was produced by running something, in the session named. Nothing is carried forward silently: if a result is old it says which session.

## Last full backend test run
- **Session 5 (Python 3.12, deps installed, network available): `pytest` = 200 passed, 0 failed.** 148 test functions, parametrised to 200 cases. Suites: contract, API, Role 1 requirement type, Role 2 resume (22), Role 3 profile (40), Role 4 formula (32) + API (8), Role 5 matching (29) + API (9), Phase 8 system (13).
- Session 4: 187 passed (before the 13 Phase 8 tests).

## Session 6 (this phase) - what was re-run, and the limit
Sandbox had **no network and no fastapi / pydantic / httpx / pytest**, so the full suite could not be re-run.
- `py_compile` of `app.py`, `radix_jd/*.py`, `tests/*.py`: **OK**.
- Pure-logic suites through a throwaway stub harness (stubs `pytest` and `radix_jd.contract` but loads the real `CATEGORIES`): `test_role4_formula.py` + `test_role5_matching.py` = **61 passed, 0 failed** (same count as Session 3).
- Not re-run this session: every test needing fastapi/pydantic/httpx (HTTP suites, Role 1-3 suites, Phase 8 system tests), the frontend build and the jsdom flow test.
- Code changed this session: **none** (docs only), so the Session 5 backend result still describes the shipped code. Re-run `pytest -q` on your machine to confirm; that is the first checklist item below.

## Frontend
- Session 4: `npm install && npx vite build` OK (168.7 kB JS / 11.2 kB CSS). jsdom flow test passed against a live local backend (`DEMO_FALLBACK=true`, no keys): JD upload -> resume parse -> level entry -> Talent Check -> Skill Match.
- Not a real browser. Nothing was clicked in Chrome/Firefox; no responsive or accessibility pass.

## Mutation checks on record (each caught, then reverted)
Old regex `requirement_type` logic (3 tests fail); placeholder evidence (1); emitting `level: 0` (2); overwrite-on-reparse (3) and ignoring dismissals (1); profile cache (1); mean over 12 instead of assessed (4); last-skill-wins (1); loose/substring fuzzy (7); no category guard (1); fuzzy counted as exact (1); duplicated route handlers (2); `DEMO_FALLBACK` default true (4); constant `match_score` / `readiness_score` (flow test); planted key (secret scan); reverting the level input to `?? 0` (UI test).

## NEVER verified (needs the user's machine / accounts)
1. **Live Gemini**: that the real model returns `requirement_type`, resume fields, and that strict grounding does not drop too many real skills. That the default model name `gemini-3.1-flash-lite` exists for the user's key.
2. **Live Supabase**: migrations applied, `on_conflict=candidate_id` upsert, RLS behaviour, `skill_set_master` -> category mapping (D5c).
3. **Official samples**: six JDs and four resumes (PDF + DOCX) were never supplied. The brief's expected pattern (Aanya SWE-leaning, Karthik data-leaning, Priya Oracle-leaning, Rohan all-rounder) is unchecked.
4. **Real browser** run of the UI; the original TS test suites (Role 1, Role 5 `engine.test.ts`).
5. The `.env`/`.venv` inside the user's `radix-jd-analytics-fixed-patch.zip` were deliberately not read. **Rotate any key that was in them.**

## Checklist for the presenter machine (in this order)
1. `cd backend && pip install -r requirements-dev.txt && pytest -q` -> expect 200 passed; record the number.
2. Set `GEMINI_API_KEY`, run the README live smoke test with 2 official JDs + 2 official resumes.
3. `cd frontend && npm install && npm run build`.
4. Run the 4 candidates x 6 JDs; confirm results differ per candidate in the direction the brief states. If they do not, that is a finding to explain, not hide.
5. Rehearse `DEMO_RUNBOOK.md` end to end.


## Session 10 — AI module review integration

- Backend regression tests: **215 passed, 0 failed**. This session added read-only Profile Builder review and optional Talent Check coaching, plus provider-fallback/privacy/validation tests.
- Python compilation: pass (`python -m compileall -q app.py radix_jd tests`).
- Frontend source syntax: Babel parse pass for `App.jsx`, `ResultsPanel.jsx`, `ProfilePanel.jsx`, `ResumePanel.jsx`, `api.js`; stylesheet PostCSS parse pass.
- Vite build: attempted but did not complete. The available `node_modules` copy lacked the Linux Rollup optional dependency `@rollup/rollup-linux-x64-gnu` (also contains Windows-built dependency files). Re-run `npm ci && npm run build && npm test` in a normal project install.
- Live Gemini/Groq/OpenRouter and Supabase: not exercised. API keys were not included in the clean source ZIP.


## Session 11 - suggestion triage and integrated evidence work (29 Oct 2026)

- Backend regression suite: **227 passed, 0 failed** after the current source changes.
- Python compilation `python -m compileall -q app.py radix_jd eval`: pass.
- Babel parser accepted every frontend JSX/JS source file. CSS opening/closing brace counts match.
- Implemented in this source: content-hash JD cache; extraction/runtime/model-call metadata; `/api/jd/stats/{jd_id}`; PyMuPDF sorted selectable-text extraction plus DOCX tables; honest evaluation harness with manually reviewed ground truth and PDF/DOCX parity; profile list/delete/completeness; JSON import/export; readiness matrix; readiness verdict rule; evidence quotes and directional implied/semantic match labels; AI profile review and readiness coach; evidence dashboard; About/Privacy/Terms; favicon and consistent font loading.
- No final precision/recall/F1 or official candidate matrix is claimed. The official six JDs and four resumes (each PDF and DOCX) are not in the pack, and `backend/eval/ground_truth/annotations.json` is intentionally empty until the team labels and second-reviews actual files.
- Frontend Vite build and real-browser check were attempted/not completed in this sandbox because its cached dependency tree lacks the Linux Rollup optional native package. No live Gemini, Groq, OpenRouter, or Supabase calls were performed in this audit. Use `npm ci && npm run build && npm test` on the presentation machine.


## Session 11 - UI pass and fresh regression test (29 Oct 2026)
- Backend: `python -m pytest -q` = **227 passed, 0 failed**.
- Frontend: Babel syntax parsing for all source `.jsx`/`.js` files passed; PostCSS CSS parse passed.
- Added Flow Control route and CSS motion/palette refinements.
- `npm ci --no-audit --no-fund` timed out in this environment. Vite production build, Vitest and browser interaction were **not** verified. Live providers/Supabase and official-data metrics also remain unverified.
