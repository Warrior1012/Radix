RADIX AI MODULE REVIEW PATCH

This patch adds:
- optional read-only AI profile review in Profile Builder
- evidence-grounded AI readiness coaching in Talent Check
- associated frontend cards/styles and offline regression tests
- configuration and documentation updates

Recommended: use the matching complete ZIP if uncertain about the current state of the local project. The patch is relative to radix-ai-provider-fallback.zip (the previous clean AI-provider integration archive).

Extract the patch at the project root and allow files to merge/overwrite. It does not contain backend/.env or API keys.

Current AI features:
- Resume Parsing: AI extraction with provider fallback
- Profile Builder: optional, read-only review (button; no auto-overwrite)
- Talent Check: deterministic score + AI recommendations
- Skill Matching: deterministic score + grounded semantic AI suggestions

After applying:
  cd backend
  python -m pytest -q
  python -m compileall -q app.py radix_jd tests

Then in another terminal:
  cd frontend
  npm ci
  npm run build
  npm test

Real API calls require valid keys in backend/.env. Do not share that file.
