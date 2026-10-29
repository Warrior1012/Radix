# Claude suggestion review: verified priorities and implementation

**Review date:** 29 October 2026  
**Source checked:** `RADIX_Talent_Match_Hackathon_Brief.pdf` (the supplied October 2026 participant brief) plus this repository and its automated tests.

## Source-boundary note

The supplied participant brief confirms the five roles, the 12-category benchmark, skill matching with an emphasis on explaining gaps, a local snapshot for three companies, and a project deadline of **28 October** followed by peer presentations on **29 October**. The supplied PDF does **not** state a 4 PM IST cutoff, the quoted 20% / 34% / 32% / 14% rubric weights, or the detailed “7b” scenario wording in the pasted recommendation. Those claims may come from a separate solution-document/rubric file, but that separate file was not provided here, so this report does not present them as verified facts.

The participant brief names **Ananya Rao**, Karthik Subramaniam, Priya Menon and Rohan Verma. Older project notes said “Aanya Rao”; current project notes and the official evaluation manifest have been corrected to “Ananya Rao”. The included Aanya Sharma testing PDF is synthetic and is not an official participant resume.

## Decision log

| Suggestion | Decision | Why / implementation |
|---|---|---|
| Human ground truth, precision/recall/F1, reproducible evaluation | **Implemented; official benchmark blocked pending inputs** | `backend/eval/` contains a manifest for all 6 official JDs and 4 official resumes, each expecting PDF and DOCX, a human annotation format, an evaluation runner and `GET /api/eval/latest`. Missing documents or labels produce blocked/partial status, never fabricated zero or final claims. Annotation must be completed and second-reviewed by the team. |
| Latency, model-call counts, provider/model metadata | **Implemented where the source path returns it** | JD and resume responses include extraction metadata; `/api/jd/stats/{jd_id}` exposes counts, cache status, latency and model calls. The evaluation runner records request latency/provider metadata when present. |
| Temperature 0 and content-hash JD cache | **Implemented** | Provider client calls use temperature 0. The content cache normalises whitespace and includes provider/model configuration in its key. Demo/keyword fallback results are not cached as AI results. |
| Robustness test suite | **Partially implemented** | Existing tests cover malformed input, provider failures/fallback, unsupported evidence, file parsing, explicit matching cases, cache behaviour, missing/unapproved evaluation labels and cross-candidate scoring. The official PDF/DOCX parity and scanned-file robustness scores still require the official files. |
| JD emphasis labels `core / standard / nice`, plus revised weighting | **Deferred** | The supplied brief requires required/preferred distinction and gap explanations, but does not define this three-level weighting taxonomy. Adding a second weighting scheme before human-labelled examples are available could change the score without demonstrated benefit. Existing required/preferred weighting stays documented. |
| `/api/jd/stats` + category bars, required/preferred split, per-skill evidence | **Implemented** | Counts come from the analysed JD. Skill rows surface extraction evidence and requirement basis. No static/fake chart values are seeded. |
| Batch analysis for six JDs | **Deferred** | No official source files were included, so batch handling could not be validated against the actual six inputs. The evaluation runner can process all configured manifest entries sequentially once paths are supplied. |
| Layout-aware PDF extraction and PDF/DOCX parity | **Partially implemented** | PyMuPDF sorted selectable-text extraction is preferred when installed; DOCX paragraphs and tables are read. The evaluation runner measures PDF/DOCX set overlap. Image-only scanned PDFs remain explicitly unsupported; direct PDF-to-Gemini/OCR was not added because it would require provider-specific binary-input handling and test documents to validate. |
| Automatically estimate resume proficiency levels | **Not implemented by design** | A resume may prove a skill exists, but does not reliably prove a calibrated 1–10 level. The parser therefore leaves confirmed `level` blank. This avoids making Talent Check numbers appear factual when inferred from keywords or years. The user can enter/confirm levels; a separately labelled, non-scoring estimate can be considered only with a clear human confirmation control and evidence basis. |
| Profile list/delete, completeness, candidate switcher, validation messaging, JSON import/export | **Implemented** | `/api/profiles`, `DELETE /api/profile/{candidate_id}`, backend-computed completeness, saved candidate selection, profile JSON import/export with basic shape checks, and a transparent AI review that does not mutate profile fields. |
| Explicit readiness definition + candidate × company matrix | **Implemented** | Verdict is `ready` only when score is at least 80, at least 6 categories are assessed, and no assessed category has a gap of 3+ levels. This is documented as a project design rule, not a hiring decision. `/api/analytics/matrix` calculates saved candidates against selected company benchmarks. |
| Radar chart / heatmap | **Partially implemented with an accessible alternative** | The Talent Check renders a real candidate-versus-company horizontal comparison across the 12 categories; Evidence & Eval has a calculated candidate × company table. These use real API results and show unassessed categories explicitly. No separate radar graphic was added, as the bar comparison is easier to read when some categories are unassessed and does not visually interpolate missing levels. |
| Semantic matching, one-way implied taxonomy, evidence quotes, learn-next | **Implemented** | Deterministic exact/alias/phrase/fuzzy matching runs first; optional AI semantic suggestions are accepted only for validated JD labels backed by candidate evidence. A directional implication such as PostgreSQL -> SQL is credited partially and must not imply SQL -> PostgreSQL. The score remains deterministic. Missing skills include `learn_next`; matched rows display evidence quotes where available. |
| Rank one candidate across six JDs | **Deferred** | This is useful for the final comparison table, but should be built against the actual six analysed JDs rather than inventing or hardcoding role records. The current single-JD match remains supported; once official files are supplied, a rank endpoint can reuse the same scorer for a meaningful comparison. |
| Evidence page, role tabs, privacy/terms, fonts, favicon and visual cleanup | **Implemented** | Added Evidence & Eval and About & Privacy navigation; Terms of Use text, consistent fonts loaded in `index.html`, favicon, square-cornered controls, flat hero background, and removal of decorative Sparkles icons and em dashes from the visible frontend source. |

## What the project can honestly claim now

- Offline backend tests run in the review workspace: **227 passed, 0 failed**.
- Python compilation passed.
- Babel syntax parsing passed for the frontend JSX/JS sources; CSS brace counts match.
- The current app code includes the evaluation instrumentation and UI components described above.

## What remains unverified

- The 6 official JD and 4 official resume files in both PDF and DOCX formats were not present. The ground-truth annotation file is intentionally empty. Therefore **no official precision, recall, F1, PDF/DOCX parity, 4-candidate × 6-JD results table, or benchmark performance claim is available yet**.
- Live Gemini, Groq, OpenRouter and Supabase calls were not executed as part of this review.
- Vite production build and actual browser UI were not verified in this sandbox because its cached `node_modules` lacks the Linux Rollup optional native package. Re-run `npm ci && npm run build && npm test` in a normal local environment.
- Scanned/image-only PDFs are not OCR'd in the current implementation.

## Suggested next steps

1. Obtain the official source pack and any separate scoring rubric/solution document from the facilitator/coordinator.
2. Have one team member annotate all ten logical documents and a second team member review the labels.
3. Configure both PDF and DOCX paths in `backend/eval/dataset/manifest.json`, run `python eval/run_eval.py --api-base http://127.0.0.1:8000` from `backend/`, and capture the resulting `latest.json` and Evidence & Eval screen.
4. Run the UI/build checks and a live model smoke test on the presentation machine.
5. Only after official inputs are present, decide whether batch JD analysis and six-JD candidate ranking are worth adding for the presentation.
