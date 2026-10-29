# Compliance matrix - official brief vs this build

Source: `RADIX_Talent_Match_Hackathon_Brief.pdf` (Oct 2026). Status legend: **Implemented+tested** = code exists and an automated test (mock Gemini / fake Supabase / synthetic fixtures) passed in a recorded session; **Not verified live** = needs real Gemini/Supabase/browser; **Open** = not done.
"Tested" never means tested against the official sample files or a live model; see `INTEGRATION_AUDIT.md`.

## Roles (brief §05)
| # | Brief requirement | Status | Where / evidence |
|---|---|---|---|
| 1 | PDF/DOCX JD -> structured skill list mapped to the 12 categories + named technologies; LLM, not plain keywords; hand off to Skill Matching | Implemented+tested; **live model not verified** | `extractor.py`, `requirement_type.py`; `test_role1_requirement_type.py`, Phase 8 flow. Required vs preferred: inline marker > section heading > model > default `required`. |
| 2 | PDF/DOCX resume -> skills + reliably extractable education/projects/experience; tolerant of layout variation; hand off to Profile Builder | Implemented+tested; **live model not verified** | `resume.py`; `test_role2_resume.py` (22). Grounding drops unsupported skills. Scanned PDFs unsupported. |
| 3 | Profile form: basic details, skills, hackathons/internships, certifications, preferred roles, CV upload; validation; save/load JSON; pre-filled from Resume Parsing; save/load early so 4 and 5 are not blocked | Implemented+tested | `contract.Profile`, `profiles.py`, `ProfilePanel.jsx`; `test_role3_profile.py` (40) incl. cross-process restart and merge-not-overwrite. Browser not exercised. |
| 4 | Saved profile + company -> readiness score + per-skillset gap over all 12; local snapshot; decide "ready" numerically | Implemented+tested | `talent_check.py`; formula in `CONTRACT.md`; `test_role4_formula.py` (32 pure, re-run Session 6: pass), `test_role4_api.py`. Decision: mean over assessed categories, floor/range disclosed. |
| 5 | One profile/resume + one JD skill list -> match score, matched + missing skills; fuzzy; gap list over the number | Implemented+tested | `skill_match.py`, `semantic_match.py`; `test_role5_matching.py`, `test_semantic_match.py`, `test_role5_api.py`. Deterministic exact/alias/phrase/fuzzy first; optional evidence-grounded semantic assist on remaining gaps, with discounted credit and labels. |

## Shared contract (brief §06)
| Item | Status |
|---|---|
| 12 codes + `OTHER`; skill = `skill_name, category_code, evidence, confidence` | Implemented (`contract.py`) |
| JD/resume result keys `source_type, source_file, company, role, skills[]` | Implemented with extensions (see `CONTRACT.md`) |
| Profile keys | Implemented (+`candidate_id, role, projects, experience, provenance`) |
| Talent Check keys `company, skillset_gap[...], readiness_score` | Implemented; **documented deviation:** `candidate_level`, `gap`, `readiness_score` may be `null` for unassessed |
| Skill Match keys `jd_source_file, match_score, matched_skills, missing_skills` | Implemented (+ richer fields) |
| "Write the contract down where everyone can see it" | `docs/CONTRACT.md` |

## Definition of done (brief §09)
| Criterion | Status |
|---|---|
| All 5 pieces run alone on >= 2 sample JDs / resumes | **Open for official files** (never supplied). Run on synthetic JD/resume fixtures only. |
| 5 pieces wired into one flow for >= 1 company/JD/candidate | Implemented+tested at API level (Phase 8 flow test, 3 companies x 3 candidates, mock Gemini); jsdom UI flow test against a live local backend (Session 4). Real browser: not done. |
| Talent Check and Skill Matching visibly differ per candidate | Implemented+tested with synthetic strong / weak / unassessed candidates; mutation-checked (constant score fails). **Not checked with Aanya/Karthik/Priya/Rohan.** |

## Stack and process (brief §09, §03, §08)
| Item | Status |
|---|---|
| Python | Yes |
| LangChain / LLM agent where it helps | Direct provider REST clients with typed errors and provider fallback; no LangChain. Roles 1-2 use LLM extraction; Role 3 offers optional read-only AI review; Role 4 offers optional AI coaching over a deterministic score; Role 5 offers optional evidence-grounded semantic matching while deterministic scoring remains authoritative. |
| React frontend | Yes (Vite, `frontend/src`) |
| Supabase, JSON for most things | Adapter + 3 additive migrations; live DB not verified. Local JSON file store otherwise. |
| Reproducible extraction evidence | Evaluation harness, human-approved annotation schema, latency/model-call metadata, PDF/DOCX parity and `/api/eval/latest`; official source files/labels are still missing, so no final metrics are claimed. |
| Quality dashboards | Evidence & Eval page shows real JD stats, saved-profile completeness and candidate × benchmark matrix; no mocked scores. |
| Live walkthrough rehearsed, 45 min | Runbook in `DEMO_RUNBOOK.md`; **rehearsal is the team's job**. |
| Milestone checklist (xlsx) | Not supplied to the build; not tracked here. |

## Open items
Supabase company-catalog mapping unverified; original TypeScript Role 1/5 tests not run here; original Lovable UI was replaced and its full parity is not verified. Scanned PDFs/OCR, six-JD batch endpoint, six-JD rank endpoint and official-data robustness metrics remain open. See `docs/CLAUDE_SUGGESTION_REVIEW.md`.
