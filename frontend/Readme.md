RADIX Talent Match — Frontend
A neo-brutalist, evidence-first interface for the existing Python FastAPI RADIX backend. The frontend never stores Gemini or Supabase service-role credentials; those belong in backend/.env only.
Run locally
From this folder:
npm install
Copy-Item .env.example .env -ErrorAction SilentlyContinue
npm run dev
Open http://localhost:5173. Start the FastAPI backend separately on http://127.0.0.1:8000 first. The browser UI includes Settings → Backend base URL; the URL is stored in this browser's local storage. The environment variable VITE_API_BASE_URL sets the default base URL at build/dev startup.
Workflow
1. Upload a JD and review required/preferred skills and evidence.
2. Upload a resume; extracted details are merged into the draft profile without replacing manual edits.
3. Review and edit the profile; enter skill levels from 1–10 explicitly. Blank means not assessed.
4. Save/load the profile.
5. Run Talent Check against a company benchmark and Skill Matching against the saved JD analysis.
API error, loading, and empty states are shown inline. If the API reports demo_keyword_fallback, the interface labels the result as demo/keyword-only rather than real AI extraction.
Browser API configuration
Default: http://127.0.0.1:8000, configurable with VITE_API_BASE_URL or the in-app settings dialog. Because this browser calls the local backend directly, the backend's CORS setting must allow http://localhost:5173. Do not set secrets in any VITE_ variable.
Tests
npm test
npm run build
The live UI flow test is opt-in through RADIX_TEST_API=http://127.0.0.1:8000; it requires a running backend. A static build does not prove Gemini or Supabase credentials work; perform the backend live smoke tests documented in the root README.