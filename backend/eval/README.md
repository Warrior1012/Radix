# Reproducible evaluation harness

Run from `backend/` with the API server already running:

```powershell
python eval/run_eval.py --api-base http://127.0.0.1:8000
```

The runner reads `eval/dataset/manifest.json`, calls `/api/analyze-jd` or `/api/parse-resume` for each existing PDF/DOCX path, compares predicted skill labels with team-authored `eval/ground_truth/annotations.json`, and saves `eval/reports/latest.json`. `/api/eval/latest` serves that exact artifact.

## Important integrity rules

- Source paths are blank until the 6 official JDs and 4 official resumes from the participant brief are provided. The runner intentionally returns `blocked` without metrics when no official documents or approved annotations are available.
- Annotations must be hand-written and independently reviewed by team members. LLM-generated ground truth is not acceptable for precision/recall claims.
- A missing document, provider failure, or absent annotation is reported as skipped/unavailable, never as zero precision or a successful test.
- Runtime and model-call counts are operational measurements, not a substitute for quality metrics.
- The existing synthetic JD/resume are useful for smoke tests, but must not be represented as results on official hackathon material.
