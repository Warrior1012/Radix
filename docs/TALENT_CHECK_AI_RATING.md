# Talent Check AI Rating

## What the UI shows
When a user runs Talent Check in the frontend, the app first requests the deterministic `/api/talent-check` result and then automatically requests `/api/talent-coach`. When a configured AI provider responds with a valid schema, the Talent Check dashboard shows a separate **AI readiness rating out of 10**, rationale, evidence notes, confidence, and coaching suggestions.

## What the rating means
- The deterministic readiness score out of 100 remains the official formula-based benchmark result.
- The AI rating is advisory and qualitative. The prompt anchors it to `readiness_score / 10`.
- Server-side validation clamps the AI rating to at most 1.5 points above or below that baseline. The model cannot overwrite the authoritative readiness score.
- Confidence is forced to `low` when fewer than 4 of the 12 categories are assessed, and forced away from `high` when fewer than 7 are assessed.
- If no category has a verified level, no AI rating is generated; the UI asks for verified assessment data first.
- If AI providers are unavailable or return invalid output, no invented rating is displayed. The deterministic score remains visible, with an AI-unavailable notice.

## Privacy and limitations
Only selected skill evidence, category-level results, and bounded project/experience summaries are supplied to the configured provider. Contact identifiers are not sent by this function. The AI rating has not been calibrated against official outcome labels and must not be interpreted as a probability of hiring or an objective scientific measurement. Provider output is validated for structure, numeric range, confidence values, and consistency with the deterministic baseline, but language and evidence rationales remain model-generated and should be reviewed.

## Tests
Offline tests verify a valid score, the low-confidence override for one assessed category, clamping to the benchmark anchor, and rejection of out-of-range values. They use mocked provider output and do not verify live model responses.
