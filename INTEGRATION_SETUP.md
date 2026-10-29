# RADIX AI + Supabase setup

## 1. Configure Gemini
1. Open Google AI Studio and create an API key.
2. In the project root, run `Copy-Item backend\.env.example backend\.env` in PowerShell (if `backend\.env` already exists, edit it instead of overwriting it).
3. Open `backend\.env` and set:
   - `GEMINI_API_KEY=your_key_here`
   - `GEMINI_MODELS=gemini-3.1-flash-lite`
   - `DEMO_FALLBACK=false`
4. Keep Groq/OpenRouter keys blank unless you intentionally want those providers too. Never put API keys in frontend variables or commit `.env`.

## 2. Configure Supabase
1. In the Supabase dashboard, copy the project URL and the backend service-role key from the project's API settings.
2. In `backend\.env`, set:
   - `SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY=YOUR_BACKEND_ONLY_KEY`
3. Do not paste the key into chat, React, or screenshots.

## 3. Apply the SQL migrations
In the same Supabase project that contains your existing `companies`, `skill_set_master`, and `company_skill_levels` tables, run these files in order in SQL Editor:
1. `supabase/migrations/20261027_create_jd_analytics_results.sql`
2. `supabase/migrations/20261028_radix_persistence.sql`

They add/ensure the JD results table and create RADIX candidate profile and assessment result tables. They do not rewrite the existing company/skill tables. If your existing `jd_analytics_results` has a different schema, stop and inspect the migration error before altering it.

## 4. Restart and verify
Restart the backend after editing `.env`:
```powershell
cd backend
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000/api/integrations/status`.

Expected:
- `ai.configured: true`, with Gemini listed.
- `supabase.connected: true`.
- `supabase.persistence_ready: true`.
- `supabase.company_catalog.complete_benchmarks` reports how many database companies could be mapped to all 12 RADIX categories.

If the company catalog count is zero, the endpoint may still reach Supabase, but the database's `skill_set_master.short_name` / `skill_set_name` values need mapping to the RADIX codes. Do not change the database schema blindly.

## 5. Verify actual functionality
- Upload a JD: `extraction_method` should identify the LLM path, not `demo_keyword_fallback`.
- Upload a resume: `extraction_method` should be `llm`.
- Save a profile, restart the backend, and load it again to prove Supabase persistence.
- Run Talent Check against one snapshot company and one company under the Supabase company benchmark optgroup.
- Run Skill Matching against the JD analysed earlier.

The three official hackathon benchmark companies remain available from the local snapshot. Complete Supabase company benchmarks are shown separately, so the official brief's expected snapshot is preserved.
