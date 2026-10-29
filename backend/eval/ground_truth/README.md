# Ground-truth annotation instructions

`annotations.json` is deliberately empty. This project currently contains synthetic test documents, not the 6 official JDs and 4 official resumes named in the participant brief. Official precision/recall must remain unavailable until those source files are supplied and a human team member annotates them.

For each `document_id` in `dataset/manifest.json`, add an entry:

```json
{
  "document_id": "google_swe_jd",
  "annotator": "team member name",
  "reviewed_by": "second team member name",
  "approved": true,
  "skills": [
    {"skill_name": "Python", "requirement_type": "required"}
  ]
}
```

For resume entries, omit `requirement_type`. Mark `approved: true` only after a human has read the full original document. Use a consistent granularity: do not label both a parent term and its synonym as separate skills unless the source clearly treats them as distinct. `skill_name` matching uses the app's explicit canonical aliases and otherwise exact normalized labels. The annotator names are part of the audit trail.

PDF and DOCX variants should share the same logical `document_id`; the evaluation runner computes extraction metrics per variant and set overlap between them. A missing variant is skipped, not counted as a pass.
