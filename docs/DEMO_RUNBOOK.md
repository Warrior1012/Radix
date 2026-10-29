# Demo runbook (45 minutes: problem, architecture, live demo, one challenge)

## Before you go on stage
- Backend + frontend running; `/api/health` shows the expected `storage_mode` and `llm_configured`.
- Decide ONE mode and say it out loud: **live Gemini** (`DEMO_FALLBACK=false`) or **offline** (`DEMO_FALLBACK=true`, labelled keyword fallback - do not present that as AI).
- Have ready: 1 official JD, 1 official resume, a second candidate (different profile) to prove results differ.
- Keep a saved profile `candidate_id` handy as a safety net if the model call fails (load, then continue from Talent Check).

## Flow (maps to the brief's integrated flow)
1. **Problem (3 min):** candidates do not know how ready they are for a *specific* job. Same 12-skillset framework as RADIX's company side.
2. **Architecture (5 min):** 5 roles, one contract (`docs/CONTRACT.md`), LLM only where it helps (Roles 1, 2), plain deterministic code for Talent Check and Skill Match.
3. **Live demo:** pick JD -> show required vs preferred + evidence + confidence -> parse resume -> show blank levels ("not assessed", never invented) -> edit profile, re-parse, show edits survive -> enter levels -> Talent Check (12 rows, status, score range) -> Skill Match (gap list first, points lost, fuzzy matches flagged) -> switch candidate, show both results change.
4. **One challenge you faced (pick one that is true):** "Every JD skill came back required" - the old logic read the heading from the evidence snippet; fixed by section-aware classification, proven by a test that fails on the old logic. Or: duplicate stale handlers silently re-bound old versions (D8a).

## Questions to be ready for
- *Why not an agent for scoring?* Harder to debug than the problem; brief says so too.
- *What does unassessed mean?* Not zero ability; score is over assessed categories, floor and range are shown.
- *What is not verified?* Say it plainly: official samples and live Supabase (see `INTEGRATION_AUDIT.md`).
