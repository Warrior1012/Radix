# RADIX Talent Match — Shared Integration Contract

This contract follows the October 2026 participant brief. The brief explicitly says this is a proposed shape for the team to review and lock; agree on it with all five role owners before final integration.

## Canonical skill object (from the brief)

```json
{
  "skill_name": "Data Structures and Algorithms",
  "category_code": "DSA",
  "evidence": "Solved graph traversal problems in project/interview practice",
  "confidence": "medium"
}
```

Allowed category codes: `DSA`, `COD`, `OOD`, `APTI`, `COMM`, `AI`, `CLOUD`, `SQL`, `SWE`, `SYSD`, `NETW`, `OS`, `OTHER`.

## Candidate profile (Role 3 → Roles 4 and 5)

```json
{
  "name": "Candidate Name",
  "email": "candidate@example.com",
  "education": "B.Tech Computer Science",
  "role": "Software Engineer Intern",
  "skills": [
    {
      "skill_name": "Data Structures and Algorithms",
      "category_code": "DSA",
      "evidence": "Solved graph traversal problems",
      "confidence": "medium",
      "level": 6
    }
  ],
  "hackathons": [],
  "internships": [],
  "certifications": [],
  "preferred_roles": ["Software Engineer Intern"],
  "cv_file": "resume.pdf"
}
```

The `level` field is an agreed integration extension, **not present in the brief's canonical skill object**. Role 4 accepts either `level` or `candidate_level` in the range 0–10. `0` or an omitted level means unassessed/missing, not a low demonstrated proficiency. Never infer a numeric level from a skill keyword alone. The team should lock how these levels are elicited/validated.

## Role 4 request

`POST /api/talent-check`

```json
{
  "candidate": { "name": "Candidate Name", "skills": [] },
  "company_id": 4
}
```

For teams that name the object `profile`, `POST /api/profile/talent-check` also accepts `{"profile": {...}, "company_id": 4}`. Both endpoints accept the `candidate` key for backwards compatibility.

## Role 4 response shape

```json
{
  "company": "Google",
  "readiness_score": 63.4,
  "skillset_gap": [
    {
      "category_code": "DSA",
      "required_level": 9,
      "candidate_level": 6,
      "gap": true,
      "gap_amount": 3
    }
  ]
}
```

The brief defines `gap` as a Boolean. `gap_amount` is an additional numeric convenience field for UI sorting and display. `gap_detected` remains as a compatibility alias for this module's existing UI. The response also includes skill names, score details, priorities, roadmap, methodology and data-source status.

## Endpoints

- `GET /api/health` — liveness and data source mode.
- `GET /api/companies` — companies, the 12 categories and data source mode.
- `POST /api/talent-check` — saved candidate + selected company.
- `POST /api/profile/talent-check` — profile-named alias for Role 3 integrations.
- `POST /api/compare` — candidate against the three bundled companies.

## Handoffs

- Role 1 JD Analytics → Role 5 Skill Matching: `{source_type, source_file, company, role, skills[]}`.
- Role 2 Resume Parsing → Role 3 Profile Builder: extracted resume details and `skills[]`.
- Role 3 Profile Builder → Role 4 Talent Check and Role 5 Skill Matching: the saved candidate profile above.
- Role 4 → integrated UI: `readiness_score` + `skillset_gap[]`.
- Role 5 → integrated UI: `match_score`, `matched_skills[]`, `missing_skills[]`.

Role 4 does not replace Role 5 and does not consume the JD skill list for its company-level readiness score.
