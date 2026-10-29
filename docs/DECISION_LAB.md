# Decision Lab: ProofGraph + What-if Simulator

Decision Lab is an additive, read-only dashboard. It does not replace or change the existing Talent Check or Skill Matching endpoints.

## ProofGraph statuses

For each required/preferred job requirement, RADIX reports one of four states based on the submitted profile and the deterministic matcher:

- **Level entered**: the matching profile skill has an explicit valid level from 1 to 10. This is an entered value, not proof of an independently administered assessment.
- **Evidence available**: a matching profile skill has evidence text but no explicit level.
- **Claimed**: a matching skill is listed, but neither evidence text nor a level is present.
- **Unassessed**: no matching skill was found in the current profile. This means unknown, not that the candidate lacks the ability.

The dashboard displays the actual evidence text, match type, requirement type, and points at risk. It never infers proficiency from keyword presence.

## What-if Simulator

A user can select one or more requirements currently missing in the deterministic match. The API makes an in-memory copy of the candidate skill list, adds those requirements as hypothetical-only entries, then reruns the same deterministic match formula (required = 2 points; preferred = 1 point).

The result includes baseline score, scenario score, score delta, selected assumptions, and an explicit explanation. Selected skills are validated against requirements that are currently missing for the supplied JD.

## Non-disruption and persistence

- New endpoints: `POST /api/decision-lab/proofgraph` and `POST /api/decision-lab/simulate`.
- Existing endpoint signatures and calculations are unchanged.
- No profile writes, Supabase writes, or saved-result writes occur for either Decision Lab endpoint.
- What-if assumptions are never stored as candidate skills, evidence, or proficiency levels.
- The scenario is not an assessment outcome, a hiring probability, or a hiring recommendation.
- The deterministic Decision Lab view does not invoke the optional AI semantic-match assist, so it remains reproducible. If the normal Skill Matching view applies semantic suggestions, its final score may differ from this audit baseline.

## Local validation

From the repository root:

```bash
cd backend
python -m pip install -r requirements.txt -r requirements-dev.txt
pytest -q
cd ../frontend
npm ci
npm run build
```

A GitHub Actions workflow runs the backend regression suite and frontend production build for this change.
