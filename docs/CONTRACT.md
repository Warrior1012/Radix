# RADIX shared data contract (code: `backend/radix_jd/contract.py`)

*Status: Phase 9 (contract unchanged since Phase 6). Checked against the official brief (supplied Session 2). The brief calls its contract a starting point; our extensions are documented here.*

## Rules
1. Join by `category_code`, never by list position. 12 benchmarked codes: `COD DSA APTI COMM OOD AI SQL SYSD CLOUD SWE NETW OS`; `OTHER` is valid on a skill only.
2. Skill object = `skill_name, category_code, evidence, confidence(high|medium|low)`. `level` (0-10 proficiency) is an agreed **extension**, never produced by extraction.
3. Unassessed proficiency is not zero-ability. **Decided Phase 3:** the `level` key is absent/`null` for unassessed; resume parsing never emits it; legacy `0` is accepted on input and normalised to `null` (Phase 4).
4. Resume skills carry extension fields `evidence_basis` (`quote|repaired_from_text`) and optionally `category_repaired`.
5. Every model failure is a typed `LLMError.kind` (auth, model_not_found, rate_limited, timeout, network, http_error, empty_response, blocked, bad_json, bad_structure).

## Profile (Role 3) validation, as enforced by `contract.Profile` / `ProfileSkill`
* skill: `skill_name` required (<=120); `category_code` in the 12 codes or `OTHER` (default `OTHER`); `confidence` high|medium|low (default low); `evidence` <=500; `level` integer 1-10 or `null` (legacy `0`/`""` -> `null`; anything else -> 422).
* profile: `name` <=100 (required on save), `email` valid format if present, `cv_file` must end `.pdf`/`.docx` if present, `candidate_id` `[A-Za-z0-9_-]{1,64}`, string lists cleaned and de-duplicated (<=50 items).
* provenance (backend-maintained): `user_edited[]`, `field_sources{}`, `dismissed{}`, per-skill `source` (`resume|manual`).
* API: `POST /api/profile` (save), `GET /api/profile/{id}`, `POST /api/profile/merge-resume` (stateless merge; never overwrites edited fields, levels or manual skills).

## Role outputs (official keys)
| Role | Required keys | Extensions kept |
|---|---|---|
| 1 JD | `source_file, company, role, skills[]` (required/preferred distinction) | `required_skills, preferred_skills, extraction_method, analysis_meta, persistence` |
| 2 Resume | profile-shaped: `name,email,education,skills[],projects,experience,certifications,...` | `parsing_method, notice` |
| 3 Profile | `name,email,education,skills[],hackathons,internships,certifications,preferred_roles,cv_file` | `candidate_id, experience, projects, role` |
| 4 Talent Check | `company, readiness_score(0-100 or null), skillset_gap[{category_code,required_level,candidate_level(1-10 or null),gap(bool or null)}]` | `gap_detected, gap_amount, skill_score, status, assessed, explanation, skills_listed, readiness_floor, score_range, provisional, coverage, unassessed_categories, ignored_skills, priority_gaps, methodology, benchmark_source` |
| 5 Skill Match | `jd_source_file, match_score(0-100 or null), matched_skills[], missing_skills[]` | `matched/missing_required_skills`, `matched/missing_preferred_skills`, `match_details[{skill,requirement_type,weight,matched,match_type,matched_with,similarity,points_*}]`, `gaps[{priority,skill,points_lost,score_impact_percent,why}]` (= `recommendations`), `exact_only_score`, `fuzzy_matches`, `jd_resolution`, `points`, `methodology` |

Open gaps vs this table: see PROJECT_STATE.md (D5a, D6b, ...).

## Talent Check formula (Role 4, Phase 5; code: `radix_jd/talent_check.py`)
Deterministic, no LLM. Benchmark = official 3-company snapshot by default (Supabase catalog is a labelled extension).
1. **Candidate level per category** = the highest explicit `level` (1-10) among the profile's skills with that `category_code` (order-independent). Skills without a level never lower it. `OTHER`/unknown codes are listed in `ignored_skills`, never scored.
2. **Assessed** = at least one levelled skill in the category. Otherwise **unassessed**: `candidate_level: null`, `gap: null`, `status: "unassessed"`, plus an explanation. It is *not* counted as zero ability.
3. `skill_score = min(candidate/required, 1) x 100` (assessed only). `status`: `meets_bar` (gap<=0), `close_gap` (1-2), `priority_gap` (>=3).
4. **`readiness_score`** = unweighted mean of assessed `skill_score`s; `null` if nothing is assessed. Label: >=80 Strong alignment, >=60 Building alignment, else Significant gaps; `Not enough assessed skills` when null; `(provisional)` appended when fewer than 6 of 12 are assessed.
5. **`readiness_floor`** = (sum of assessed scores)/12, i.e. the worst case if every unassessed category were zero. `score_range` reports both.
6. Out-of-range levels are rejected at the profile layer (422); the calculator itself treats anything outside 1-10 as unassessed (never clamps).
Persistence: results go to `radix_talent_check_results` with `company_ref` (`snapshot:<id>` / `supabase:<id>`); `company_id` is the numeric id or NULL.
Breaking change vs Phase 4: an empty / unlevelled profile now returns `readiness_score: null` (was `0`).

## Skill Matching (Role 5, Phase 6; code: `radix_jd/skill_match.py`)
* Request: `POST /api/skill-match {profile, job?, jd_id?}`. With `jd_id` the server loads the analysed JD (local `data/jds/` store -> in-process cache -> Supabase `jd_analytics_results.id`) and its stored lists win over client-sent lists; `jd_resolution` says which path was used (`jd_id`, `request`, `jd_id_not_found_used_request_lists`). Unknown `jd_id` with no lists = 404; bad id = 400; neither `jd_id` nor `job` = 422.
* Each JD skill is matched in order: `exact` (cleaned text) -> `alias` (explicit synonym map ported from the original TS engine) -> `fuzzy` (difflib >= 0.88; both names >= 5 chars, same first letter, identical digits; blocked between two known different skills and between two different RADIX categories). No substring matching.
* Score = earned/possible x 100, required = 2, preferred = 1, 2 decimals; a skill in both lists counts once as required; `null` + `unable_to_calculate` if the JD has no skills. Fuzzy matches count but are listed in `fuzzy_matches`; `exact_only_score` excludes them.
* Gap list (`gaps`) is the primary output: priority, `points_lost`, `score_impact_percent`, plain-language `why`.
* `jd_id` is the local uuid returned by `/api/analyze-jd`; the Supabase row id (`persistence.id`) is also resolvable. Local JD files are git-ignored and excluded from zips.
