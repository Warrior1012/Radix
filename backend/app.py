"""RADIX Talent Match unified API: thin wiring. Logic lives in radix_jd/* (see PROJECT_STATE.md)."""
from __future__ import annotations
import os, re, uuid, time, json
from typing import Any
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
# Names below are re-exported on purpose: tests and other modules patch/import them from `app`.
from radix_jd.contract import CATEGORIES, Profile
from radix_jd.benchmarks import load_benchmarks, BENCHMARK_PATH  # noqa: F401
from radix_jd.documents import safe_filename, extract_text, extract_text_with_metadata, MAX_TEXT_CHARS  # noqa: F401
from radix_jd.extractor import configured_targets, extract_with_llm, demo_extract, demo_fallback_enabled  # noqa: F401
from radix_jd.gemini import LLMError
from radix_jd.requirement_type import resolve_requirement_type
from radix_jd.resume import parse_resume_llm, skill_category, keyword_fallback_data, build_resume_profile, compare_resume_extractions  # noqa: F401
from radix_jd.skill_match import compute_skill_match, canonical, ALIASES  # noqa: F401
from radix_jd.semantic_match import suggest_semantic_matches
from radix_jd.jd_store import FileJDStore, InvalidJDId, jd_from_row
from radix_jd.jd_cache import JDExtractionCache, make_cache_key
JD_STORE=FileJDStore()
JD_CACHE=JDExtractionCache()
from radix_jd.supabase_store import SupabaseStore
from radix_jd.profiles import (ProfileRepository, InvalidCandidateId, detect_user_edits, merge_resume_into_profile, now_iso, validate_for_save)
from radix_jd.talent_check import compute_talent_check
from radix_jd.talent_coach import generate_talent_coaching
from radix_jd.profile_review import generate_profile_review
from radix_jd.decision_lab import build_proof_graph, simulate_skill_match

load_dotenv(Path(__file__).parent / '.env')
app = FastAPI(title='RADIX Talent Match — Unified API', version='1.1.0')
origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['*'], allow_headers=['*'])
MAX_UPLOAD_MB=int(os.getenv('MAX_UPLOAD_MB','8'))
COMPANIES = load_benchmarks()
JDS: dict[str, dict[str, Any]] = {}  # analysed JDs by jd_id (in-process cache; Role 5 resolves jd_id in Phase 6)
STORE = SupabaseStore.from_env()
PROFILE_REPO = ProfileRepository(STORE)  # durable store only; no in-process cache can mask it (D4c)

class CheckRequest(BaseModel):
    profile: Profile
    company_id: str | int
class MatchRequest(BaseModel):
    profile: Profile
    job: dict[str, Any] | None = None
    jd_id: str | None = None

class DecisionLabRequest(BaseModel):
    profile: Profile
    job: dict[str, Any] | None = None
    jd_id: str | None = None
    assumed_skills: list[str] = Field(default_factory=list, max_length=25)

class MatrixRequest(BaseModel):
    candidate_ids: list[str] = Field(default_factory=list, max_length=50)
    company_ids: list[str | int] | None = None

@app.get('/')
def root(): return {'message':'RADIX Talent Match Unified API','docs':'/docs','status':'ready'}
@app.get('/api/health')
def health():
    targets = configured_targets()
    return {'status':'ok','llm_configured':bool(targets),'providers':[{'provider':t['provider'],'model':t['model']} for t in targets], 'demo_fallback':demo_fallback_enabled(),'storage_mode':'supabase' if STORE.configured else 'local-file','modules':['jd-analytics','resume-parsing','profile-builder','talent-check','skill-matching']}

@app.get('/api/integrations/status')
def integration_status():
    """Report configuration and read-only connectivity checks without exposing secrets."""
    targets = configured_targets()
    ai = {
        'configured': bool(targets),
        'providers': [{'provider': t['provider'], 'model': t['model']} for t in targets],
        'features': {
            'jd_analytics': bool(targets),
            'resume_parsing': bool(targets),
            'profile_review': bool(targets) and os.getenv('AI_PROFILE_REVIEW', 'true').strip().lower() in {'1', 'true', 'yes', 'on'},
            'talent_coaching': bool(targets) and os.getenv('AI_TALENT_COACHING', 'true').strip().lower() in {'1', 'true', 'yes', 'on'},
            'semantic_skill_matching': bool(targets) and os.getenv('AI_SEMANTIC_MATCHING', 'true').strip().lower() in {'1', 'true', 'yes', 'on'},
        },
        'note': 'JD/resume extraction, optional profile review, readiness coaching, and evidence-grounded semantic matching use the configured server-side providers. Resume parsing tries the configured providers in RESUME_PROVIDER_ORDER.' if targets else 'Add GEMINI_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY to backend/.env and restart.'
    }
    if not STORE.configured:
        supabase = {'configured': False, 'connected': False, 'tables': [], 'note': 'Add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to backend/.env, then restart.'}
    else:
        checks = [STORE.check_table('companies', 'company_id,name,short_name'),
                  STORE.check_table('skill_set_master', 'skill_set_id,skill_set_name,short_name'),
                  STORE.check_table('company_skill_levels', 'company_id,skill_set_id,required_level'),
                  STORE.check_table('jd_analytics_results', 'id,source_type,source_file,skills'),
                  STORE.check_table('radix_candidate_profiles', 'candidate_id,profile'),
                  STORE.check_table('radix_talent_check_results', 'id,candidate_id,company_id,result'),
                  STORE.check_table('radix_skill_match_results', 'id,candidate_id,job_id,result')]
        company_catalog = {'available': False, 'complete_benchmarks': 0, 'note': 'Company tables have not been queried.'}
        if all(x['ok'] for x in checks[:3]):
            try:
                live_benchmarks = STORE.list_company_benchmarks()
                company_catalog = {'available': bool(live_benchmarks), 'complete_benchmarks': len(live_benchmarks), 'note': 'Only companies with a complete, mapped set of all 12 RADIX categories are offered in the selector.'}
            except Exception as exc:
                company_catalog = {'available': False, 'complete_benchmarks': 0, 'note': f'Could not map company skill rows ({type(exc).__name__}). Check skill_set_master.short_name / skill_set_name mappings.'}
        supabase = {'configured': True, 'connected': all(x['ok'] for x in checks[:3]), 'tables': checks, 'persistence_ready': all(x['ok'] for x in checks[3:]), 'company_catalog': company_catalog, 'note': 'Company benchmark schema and RADIX persistence tables are checked independently.'}
    return {'ai': ai, 'supabase': supabase, 'benchmark_source': 'official three-company snapshot plus optional live Supabase company benchmarks', 'secrets_exposed': False}
@app.get('/api/companies')
def companies():
    # Keep the three required hackathon snapshot companies visible; append valid live
    # database-backed companies when Supabase is configured. Source is explicit so IDs
    # from the two sources can never collide.
    result = [{ 'company_id': c['company_id'], 'name': c['name'], 'short_name': c['short_name'], 'source': 'snapshot' } for c in COMPANIES]
    if STORE.configured:
        try:
            result.extend([{**{k: c[k] for k in ('name','short_name')}, 'company_id': f"supabase:{c['company_id']}", 'source': 'supabase'} for c in STORE.list_company_benchmarks()])
        except Exception:
            # Do not take down the official hackathon flow if optional DB catalog tables
            # are unavailable; /api/integrations/status reports the underlying problem.
            pass
    return result
@app.post('/api/analyze-jd')
async def analyze_jd(file: UploadFile=File(...), company: str=Form(default=''), role: str=Form(default='')):
    started = time.perf_counter()
    filename=safe_filename(file.filename or 'job-description.pdf'); content=await file.read()
    if len(content)>MAX_UPLOAD_MB*1024*1024: raise HTTPException(413,f'File exceeds {MAX_UPLOAD_MB} MB.')
    text, document_meta = extract_text_with_metadata(filename, content)
    targets = configured_targets()
    cache_key = make_cache_key(text, targets) if targets else None
    extracted = JD_CACHE.get(cache_key) if cache_key else None
    cache_hit = extracted is not None
    if cache_hit:
        extracted = dict(extracted)
        cached_meta = dict(extracted.get('analysis_meta') or {})
        cached_meta.update({'cache_hit': True, 'model_calls': 0, 'cache_key_prefix': cache_key[:12]})
        extracted['analysis_meta'] = cached_meta
    else:
        try: extracted=await extract_with_llm(text)
        except RuntimeError as exc: raise HTTPException(502,str(exc)) from exc
        if cache_key and extracted:
            JD_CACHE.put(cache_key, extracted)
    skills=[]; basis_counts: dict[str,int]={}; corrections=0
    for s in extracted.get('skills',[]):
        item=dict(s); model_value=item.get('requirement_type')
        rtype,basis=resolve_requirement_type(model_value,item.get('evidence',''),text)
        if model_value in ('required','preferred') and model_value!=rtype: corrections+=1
        item['requirement_type']=rtype; item['requirement_basis']=basis; basis_counts[basis]=basis_counts.get(basis,0)+1
        skills.append(item)
    meta=dict(extracted.get('analysis_meta',{})); meta['requirement_basis_counts']=basis_counts; meta['requirement_type_corrections']=corrections
    meta['document_extraction'] = document_meta
    meta['cache_hit'] = cache_hit
    meta['model_calls'] = 0 if cache_hit else len(meta.get('models_invoked') or [])
    meta['runtime_ms'] = round((time.perf_counter() - started) * 1000, 2)
    result={'jd_id':str(uuid.uuid4()),'source_type':'jd','source_file':filename,'company':company.strip() or extracted.get('company'),'role':role.strip() or extracted.get('role'),'skills':skills,'required_skills':[s['skill_name'] for s in skills if s['requirement_type']=='required'],'preferred_skills':[s['skill_name'] for s in skills if s['requirement_type']=='preferred'],'extraction_method':extracted.get('extraction_method','unknown'),'analysis_meta':meta}
    JDS[result['jd_id']]=result
    try: JD_STORE.save(result)
    except Exception as exc: result['jd_store_warning']=f'JD analysed but not saved locally ({type(exc).__name__}); Skill Matching by jd_id may fail after a restart.'
    if STORE.configured:
        try:
            result['persistence'] = STORE.insert_jd_result({**result, 'skills': skills})
        except Exception as exc:
            result['persistence']={'saved':False,'mode':'supabase','warning':f'JD analysis succeeded, but saving failed ({type(exc).__name__}). Check jd_analytics_results permissions/schema.'}
    else:
        result['persistence']={'saved':False,'mode':'memory-demo','warning':'Supabase is not configured; JD results are not persisted.'}
    return result
@app.post('/api/parse-resume')
async def parse_resume(file: UploadFile=File(...)):
    started = time.perf_counter()
    filename=safe_filename(file.filename or 'resume.pdf'); content=await file.read()
    if len(content)>MAX_UPLOAD_MB*1024*1024: raise HTTPException(413,f'File exceeds {MAX_UPLOAD_MB} MB.')
    text, document_meta = extract_text_with_metadata(filename, content)
    fallback_reason=None
    try:
        data=await parse_resume_llm(text)
    except LLMError as exc:
        data=None; fallback_reason=f'{exc.kind}: {exc}'
    if data is None and fallback_reason is None:
        fallback_reason='no AI provider configured (add a supported provider key to backend/.env)'
    method='llm' if data else 'demo_keyword_fallback'
    if not data and not demo_fallback_enabled():
        raise HTTPException(502, f'AI resume parsing failed - {fallback_reason}. No keyword fallback was used (DEMO_FALLBACK=false).')
    if not data: data=keyword_fallback_data(text)
    profile=build_resume_profile(data, method, filename, len(text), text=text, fallback_reason=fallback_reason)
    ai_attempts = data.get('_ai_attempts') if data else None
    used_model = data.get('_model') if data else None
    ai_metadata = {'model_used': used_model, **(ai_attempts or {})} if data else {'model_used': None, 'fallback_used': True, 'mode': 'keyword_fallback', 'reason': fallback_reason}
    ai_metadata['model_calls'] = len(ai_metadata.get('attempted') or [])
    ai_metadata['runtime_ms'] = round((time.perf_counter() - started) * 1000, 2)
    return {'source_type':'resume','source_file':filename,'profile':profile,'extraction_method':method,
            'document_extraction': document_meta, 'ai_metadata': ai_metadata}
@app.post('/api/parse-resume/compare')
async def compare_parsed_resume(file: UploadFile=File(...), primary_model: str=Form(...), primary_skills: str=Form(...)):
    """Run an explicit second-provider extraction and compare skill overlap without changing the profile."""
    filename=safe_filename(file.filename or 'resume.pdf')
    content=await file.read()
    if len(content)>MAX_UPLOAD_MB*1024*1024:
        raise HTTPException(413,f'File exceeds {MAX_UPLOAD_MB} MB.')
    text, document_meta = extract_text_with_metadata(filename, content)
    try:
        submitted_skills=json.loads(primary_skills)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, 'primary_skills must contain valid JSON.') from exc
    if not isinstance(submitted_skills, list):
        raise HTTPException(422, 'primary_skills must be a JSON array.')
    try:
        result=await compare_resume_extractions(text, submitted_skills, primary_model)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMError as exc:
        status=409 if exc.kind == 'comparison_unavailable' else 502
        raise HTTPException(status, f'Cross-provider comparison unavailable: {exc.kind}: {exc}') from exc
    return {
        'source_type': 'resume_comparison',
        'source_file': filename,
        'document_extraction': document_meta,
        **result,
    }

class MergeRequest(BaseModel):
    profile: dict[str, Any] | None = None
    parsed: dict[str, Any]
@app.post('/api/profile')
def save_profile(profile: Profile):
    errors=validate_for_save(profile)
    if errors: raise HTTPException(422, errors)
    key=profile.candidate_id or uuid.uuid4().hex
    item=profile.model_dump(); item['candidate_id']=key
    try: previous=PROFILE_REPO.get(key)
    except Exception as exc: raise HTTPException(503, f'Could not read the stored profile before saving ({type(exc).__name__}). Check storage configuration.') from exc
    item.update(detect_user_edits(previous, item)); item['saved_at']=now_iso()
    try: PROFILE_REPO.save(item)
    except Exception as exc:
        raise HTTPException(503, f'Profile persistence failed on {PROFILE_REPO.mode} ({type(exc).__name__}). ' + ('Apply the provided migration and verify backend credentials.' if STORE.configured else 'Check that the backend can write to PROFILE_STORE_DIR.')) from exc
    out={'saved':True,'profile':item,'storage':PROFILE_REPO.mode,'completeness':_profile_completeness(item)}
    if not STORE.configured: out['warning']='Saved to a local file on the backend machine. Configure Supabase for shared, hosted persistence.'
    return out
@app.get('/api/profile/{candidate_id}')
def get_profile(candidate_id: str):
    try: item=PROFILE_REPO.get(candidate_id)
    except InvalidCandidateId: raise HTTPException(400,'Invalid candidate id.')
    except Exception as exc: raise HTTPException(503, f'Profile load failed on {PROFILE_REPO.mode} ({type(exc).__name__}). Check storage configuration.') from exc
    if item is None: raise HTTPException(404,'Profile not found. Save the profile first.')
    return item
def _profile_completeness(profile: dict[str, Any]) -> dict[str, Any]:
    fields = {
        'name': bool(str(profile.get('name') or '').strip()),
        'education': bool(str(profile.get('education') or '').strip()),
        'skills': bool(profile.get('skills')),
        'skill_evidence': any(str(s.get('evidence') or '').strip() for s in (profile.get('skills') or []) if isinstance(s, dict)),
        'level_assessment': any(s.get('level') is not None for s in (profile.get('skills') or []) if isinstance(s, dict)),
        'projects': bool(profile.get('projects')),
        'experience_or_internship': bool(profile.get('experience') or profile.get('internships')),
        'preferred_roles': bool(profile.get('preferred_roles')),
    }
    score = round(sum(fields.values()) / len(fields) * 100)
    return {'score': score, 'completed_fields': sum(fields.values()), 'total_fields': len(fields), 'fields': fields}


@app.get('/api/profiles')
def list_profiles():
    """List saved candidate summaries only; full profile details are fetched separately."""
    try:
        rows = PROFILE_REPO.list()
    except Exception as exc:
        raise HTTPException(503, f'Profile list failed on {PROFILE_REPO.mode} ({type(exc).__name__}).') from exc
    return {'profiles': [
        {'candidate_id': p.get('candidate_id'), 'name': p.get('name') or 'Unnamed candidate',
         'saved_at': p.get('saved_at'), 'skills_count': len(p.get('skills') or []),
         'completeness': _profile_completeness(p)} for p in rows
    ], 'storage': PROFILE_REPO.mode}


@app.delete('/api/profile/{candidate_id}')
def delete_profile(candidate_id: str):
    try:
        existing = PROFILE_REPO.get(candidate_id)
        if existing is None:
            raise HTTPException(404, 'Profile not found.')
        PROFILE_REPO.delete(candidate_id)
    except InvalidCandidateId:
        raise HTTPException(400, 'Invalid candidate id.')
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f'Profile deletion failed on {PROFILE_REPO.mode} ({type(exc).__name__}).') from exc
    return {'deleted': True, 'candidate_id': candidate_id}


@app.post('/api/profile/merge-resume')
def merge_resume(req: MergeRequest):
    """Merge a parsed resume into the current profile without overwriting the person's edits. Does not save; the client saves."""
    try: merged, report = merge_resume_into_profile(req.profile, req.parsed)
    except ValueError as exc: raise HTTPException(422, f'Invalid profile: {exc}') from exc
    return {'profile': merged, 'report': report}


@app.post('/api/profile-review')
async def profile_review(profile: Profile):
    """Read-only AI suggestions for profile completeness; never mutates or saves the submitted profile."""
    return await generate_profile_review(profile.model_dump())
def _resolve_talent_company(requested_id: str | int):
    """Resolve a complete company benchmark for both scoring and AI coaching."""
    benchmark_source = 'snapshot'
    resolved_company_id: int | None = None
    company = None
    requested = str(requested_id)
    if requested.startswith('supabase:'):
        if not STORE.configured:
            raise HTTPException(503, 'Supabase is not configured.')
        raw_id = requested.split(':', 1)[1]
        try:
            db_companies = STORE.list_company_benchmarks()
            company = next((c for c in db_companies if str(c['company_id']) == raw_id), None)
        except Exception as exc:
            raise HTTPException(503, f'Could not load company benchmarks from Supabase ({type(exc).__name__}). Check company_skill_levels and skill_set_master mappings.') from exc
        if company:
            benchmark_source = 'supabase'
            resolved_company_id = int(company['company_id']) if str(company['company_id']).isdigit() else None
    else:
        try:
            numeric_id = int(requested_id)
        except (TypeError, ValueError):
            numeric_id = -1
        company = next((c for c in COMPANIES if c['company_id'] == numeric_id), None)
        resolved_company_id = numeric_id if company else None
    if not company:
        raise HTTPException(404, 'Company not found or no complete 12-skillset benchmark is available for it.')
    return company, benchmark_source, resolved_company_id


@app.post('/api/talent-check')
def talent_check(req: CheckRequest):
    started = time.perf_counter()
    company, benchmark_source, resolved_company_id = _resolve_talent_company(req.company_id)
    calc = compute_talent_check(req.profile.skills_as_dicts(), company)
    result = {'candidate_name': req.profile.name, 'candidate_id': req.profile.candidate_id,
              'company': company['short_name'], 'company_id': req.company_id,
              'benchmark_source': benchmark_source, 'runtime_ms': round((time.perf_counter() - started) * 1000, 2), **calc}
    if STORE.configured:
        try:
            company_ref = ('supabase:' if benchmark_source == 'supabase' else 'snapshot:') + str(
                resolved_company_id if benchmark_source != 'supabase' else str(req.company_id).split(':', 1)[1]
            )
            result['persistence'] = STORE.insert_result('radix_talent_check_results', {
                'candidate_id': req.profile.candidate_id, 'company_id': resolved_company_id,
                'company_ref': company_ref, 'result': result,
            })
        except Exception as exc:
            result['persistence'] = {'saved': False, 'mode': 'supabase', 'warning': f'Result not saved ({type(exc).__name__}); apply the provided migration.'}
    else:
        result['persistence'] = {'saved': False, 'mode': 'memory-demo'}
    return result


@app.post('/api/talent-coach')
async def talent_coach(req: CheckRequest):
    """Generate optional AI coaching from a freshly computed, authoritative Talent Check."""
    company, _, _ = _resolve_talent_company(req.company_id)
    calc = compute_talent_check(req.profile.skills_as_dicts(), company)
    return {
        'company': company['short_name'],
        'readiness_score': calc['readiness_score'],
        'skills_assessed': calc['skills_assessed'],
        **await generate_talent_coaching(req.profile.model_dump(), company['short_name'], calc),
    }


def resolve_jd(jd_id: str) -> dict[str, Any] | None:
    """Find an analysed JD: durable local store first, then the in-process cache, then Supabase (by row id)."""
    try: jd=JD_STORE.get(jd_id)
    except InvalidJDId: raise HTTPException(400,'Invalid jd_id.')
    except Exception as exc: raise HTTPException(503,f'JD store read failed ({type(exc).__name__}).') from exc
    if jd is None: jd=JDS.get(jd_id)
    if jd is None and STORE.configured:
        try: row=STORE.get_jd_result(jd_id)
        except Exception as exc: raise HTTPException(503,f'Could not load the JD from Supabase ({type(exc).__name__}).') from exc
        jd=jd_from_row(row) if row else None
    return jd
@app.get('/api/jd/stats/{jd_id}')
def jd_stats(jd_id: str):
    """Return counts derived from a saved JD analysis; no chart/demo values are hard-coded."""
    jd = resolve_jd(jd_id)
    if not jd:
        raise HTTPException(404, 'Analysed JD not found.')
    from collections import Counter
    skills = [s for s in (jd.get('skills') or []) if isinstance(s, dict)]
    categories = Counter(str(s.get('category_code') or 'OTHER').upper() for s in skills)
    requirements = Counter(str(s.get('requirement_type') or 'required') for s in skills)
    confidence = Counter(str(s.get('confidence') or 'low').lower() for s in skills)
    return {
        'jd_id': jd.get('jd_id'), 'source_file': jd.get('source_file'),
        'total_skills': len(skills), 'required': requirements.get('required', 0),
        'preferred': requirements.get('preferred', 0),
        'category_counts': dict(sorted(categories.items())),
        'requirement_counts': {k: requirements.get(k, 0) for k in ('required', 'preferred')},
        'confidence_counts': {k: confidence.get(k, 0) for k in ('high', 'medium', 'low')},
        'runtime_ms': (jd.get('analysis_meta') or {}).get('runtime_ms'),
        'cache_hit': (jd.get('analysis_meta') or {}).get('cache_hit', False),
        'model_calls': (jd.get('analysis_meta') or {}).get('model_calls', 0),
    }


@app.post('/api/analytics/matrix')
def analytics_matrix(req: MatrixRequest):
    """Compute saved-candidate x company readiness in one request for comparison views."""
    if not req.candidate_ids:
        raise HTTPException(422, 'Provide at least one saved candidate_id.')
    companies_to_score = req.company_ids or [c['company_id'] for c in COMPANIES]
    matrix = []
    for candidate_id in req.candidate_ids:
        try:
            profile_data = PROFILE_REPO.get(candidate_id)
        except InvalidCandidateId:
            raise HTTPException(400, f'Invalid candidate id: {candidate_id}')
        if profile_data is None:
            matrix.append({'candidate_id': candidate_id, 'candidate_name': None, 'error': 'profile_not_found', 'results': []})
            continue
        profile = Profile.model_validate(profile_data)
        results = []
        for company_id in companies_to_score:
            company, source, _ = _resolve_talent_company(company_id)
            scored = compute_talent_check(profile.skills_as_dicts(), company)
            results.append({'company_id': company_id, 'company': company['short_name'], 'benchmark_source': source,
                            'readiness_score': scored['readiness_score'], 'skills_assessed': scored['skills_assessed'],
                            'readiness_label': scored['readiness_label'], 'readiness_verdict': scored['readiness_verdict']})
        matrix.append({'candidate_id': candidate_id, 'candidate_name': profile.name, 'results': results})
    return {'matrix': matrix, 'companies_count': len(companies_to_score), 'candidates_count': len(req.candidate_ids)}


@app.get('/api/eval/latest')
def latest_evaluation():
    """Serve the latest evaluation artifact if one exists; never invent scores when labels are absent."""
    path = Path(__file__).resolve().parent / 'eval' / 'reports' / 'latest.json'
    if not path.exists():
        return {'available': False, 'status': 'not_run', 'metrics': None,
                'message': 'No evaluation report exists yet. Add official sample documents and team-authored ground truth, then run backend/eval/run_eval.py.'}
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise HTTPException(500, 'The latest evaluation report is unreadable.')
    return {'available': True, **result}


@app.post('/api/skill-match')
async def skill_match(req: MatchRequest):
    started = time.perf_counter()
    job=dict(req.job or {}); resolution='request'
    if req.jd_id:
        jd=resolve_jd(req.jd_id)
        if jd:
            job={**job,'job_id':req.jd_id,'required_skills':jd.get('required_skills',[]),'preferred_skills':jd.get('preferred_skills',[]),'skills':jd.get('skills'),'source_file':jd.get('source_file'),'company':jd.get('company'),'role':jd.get('role')}
            resolution='jd_id'
        elif job.get('required_skills') or job.get('preferred_skills'): resolution='jd_id_not_found_used_request_lists'
        else: raise HTTPException(404,'Analysed JD not found. Analyse the JD again, or send required_skills/preferred_skills.')
    elif not req.job: raise HTTPException(422,'Send either jd_id or job.')

    candidate_skills=[s for s in req.profile.skills_as_dicts() if s.get('skill_name')]
    calc=compute_skill_match(candidate_skills, job)
    ai_assist={"enabled": False, "applied": False, "fallback_used": True, "reason": "No deterministic gaps to resolve."}
    if calc.get('missing_skills'):
        semantic_map, ai_assist = await suggest_semantic_matches(candidate_skills, job, calc['missing_skills'])
        if semantic_map:
            calc=compute_skill_match(candidate_skills, job, semantic_matches=semantic_map)
    result={'module':'skill-matching','version':'1.3.0','runtime_ms': round((time.perf_counter() - started) * 1000, 2),'job_id':job.get('job_id','uploaded-jd'),'jd_source_file':job.get('jd_source_file') or job.get('source_file') or 'uploaded-jd','jd_resolution':resolution,'company_id':job.get('company_id'),'candidate_id':req.profile.candidate_id,'ai_assist':ai_assist,**calc}
    if STORE.configured:
        try: result['persistence']=STORE.insert_result('radix_skill_match_results', {'candidate_id':req.profile.candidate_id, 'job_id':str(result['job_id']), 'company_id':job.get('company_id'), 'result':result})
        except Exception as exc: result['persistence']={'saved':False,'mode':'supabase','warning':f'Result not saved ({type(exc).__name__}); apply the provided migration.'}
    else: result['persistence']={'saved':False,'mode':'memory-demo'}
    return result


# Decision Lab endpoints are deliberately additive and stateless. They do not write
# candidate profiles or result tables, so existing deployed workflows remain unchanged.
def _resolve_decision_lab_job(req: DecisionLabRequest) -> tuple[dict[str, Any], str]:
    job = dict(req.job or {})
    resolution = "request"
    if req.jd_id:
        jd = resolve_jd(req.jd_id)
        if jd:
            job = {
                **job,
                "job_id": req.jd_id,
                "required_skills": jd.get("required_skills", []),
                "preferred_skills": jd.get("preferred_skills", []),
                "skills": jd.get("skills"),
                "source_file": jd.get("source_file"),
                "company": jd.get("company"),
                "role": jd.get("role"),
            }
            resolution = "jd_id"
        elif job.get("required_skills") or job.get("preferred_skills"):
            resolution = "jd_id_not_found_used_request_lists"
        else:
            raise HTTPException(404, "Analysed JD not found. Analyse the JD again, or send required_skills/preferred_skills.")
    elif not req.job:
        raise HTTPException(422, "Send either jd_id or job.")

    if not job.get("required_skills") and not job.get("preferred_skills"):
        raise HTTPException(422, "The job description has no required or preferred skills to compare.")
    return job, resolution


@app.post("/api/decision-lab/proofgraph")
def decision_lab_proofgraph(req: DecisionLabRequest):
    """Return a non-persisted requirement-to-evidence view for the submitted profile and JD."""
    job, resolution = _resolve_decision_lab_job(req)
    result = build_proof_graph(req.profile.skills_as_dicts(), job)
    return {
        "module": "decision-lab-proofgraph",
        "job_id": job.get("job_id") or req.jd_id or "request-job",
        "job_role": job.get("role") or job.get("job_title") or "",
        "job_company": job.get("company") or "",
        "jd_resolution": resolution,
        "candidate_name": req.profile.name,
        "profile_saved": False,
        **result,
    }


@app.post("/api/decision-lab/simulate")
def decision_lab_simulate(req: DecisionLabRequest):
    """Calculate a hypothetical skill-demonstration scenario without mutating or persisting the profile."""
    job, resolution = _resolve_decision_lab_job(req)
    try:
        result = simulate_skill_match(
            req.profile.skills_as_dicts(),
            job,
            req.assumed_skills,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "module": "decision-lab-simulation",
        "job_id": job.get("job_id") or req.jd_id or "request-job",
        "job_role": job.get("role") or job.get("job_title") or "",
        "job_company": job.get("company") or "",
        "jd_resolution": resolution,
        "candidate_name": req.profile.name,
        **result,
    }
