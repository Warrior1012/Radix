from __future__ import annotations
import os
from typing import Any
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

SKILLS = [
    {'id': 1, 'name': 'Coding', 'code': 'COD'},
    {'id': 2, 'name': 'Data Structures and Algorithms', 'code': 'DSA'},
    {'id': 3, 'name': 'Aptitude and Problem Solving', 'code': 'APTI'},
    {'id': 4, 'name': 'Communication Skills', 'code': 'COMM'},
    {'id': 5, 'name': 'Object-Oriented Programming and Design', 'code': 'OOD'},
    {'id': 6, 'name': 'AI Native Engineering', 'code': 'AI'},
    {'id': 7, 'name': 'SQL and Design', 'code': 'SQL'},
    {'id': 8, 'name': 'System Design and Architecture', 'code': 'SYSD'},
    {'id': 9, 'name': 'DevOps and Cloud', 'code': 'CLOUD'},
    {'id': 10, 'name': 'Software Engineering', 'code': 'SWE'},
    {'id': 11, 'name': 'Computer Networking', 'code': 'NETW'},
    {'id': 12, 'name': 'Operating System', 'code': 'OS'},
]
COMPANIES = [
    {'company_id': 4, 'name': 'Google LLC', 'short_name': 'Google'},
    {'company_id': 78, 'name': 'Microsoft Corporation', 'short_name': 'Microsoft'},
    {'company_id': 24, 'name': 'Oracle Financial Services Software Limited', 'short_name': 'Oracle Financial Services'},
]
# Seeded from the current Bootcamp2 company_skill_levels snapshot retrieved for the hackathon companies.
# If live Supabase reads succeed, the live table is used instead.
DEMO_LEVELS = {
  4: [8,9,9,7,8,7,8,4,9,9,9,9],
  78: [6,9,8,7,8,8,8,8,7,9,8,8],
  24: [5,6,6,6,6,6,6,5,5,7,5,5],
}

app = FastAPI(title='RADIX Talent Check API', version='1.0.0')
origins = [x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['*'])


def sb_get(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError('Supabase URL/key not configured')
    response = requests.get(
        f'{SUPABASE_URL}/rest/v1/{table}', params=params, timeout=5,
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Accept': 'application/json'}
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f'Unexpected Supabase response for {table}')
    return data


def company_and_levels() -> tuple[list[dict[str, Any]], dict[int, list[int]], str, str | None]:
    """Try live Bootcamp2 data; fail safely to a clearly labelled local snapshot."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            company_rows = sb_get('companies', {'select':'company_id,name,short_name','company_id':'in.(4,78,24)','order':'company_id.asc'})
            skill_rows = sb_get('skill_set_master', {'select':'skill_set_id,skill_set_name,short_name','order':'skill_set_id.asc'})
            level_rows = sb_get('company_skill_levels', {'select':'company_id,skill_set_id,required_level','company_id':'in.(4,78,24)','order':'company_id.asc,skill_set_id.asc'})
            if company_rows and skill_rows and level_rows:
                levels: dict[int, list[int]] = {}
                for row in level_rows:
                    cid, sid = int(row['company_id']), int(row['skill_set_id'])
                    levels.setdefault(cid, [0] * 12)
                    if 1 <= sid <= 12:
                        levels[cid][sid - 1] = int(row['required_level'])
                if all(len(levels.get(cid, [])) == 12 and all(v > 0 for v in levels[cid]) for cid in (4,78,24)):
                    company_rows = sorted(company_rows, key=lambda c: [4,78,24].index(int(c['company_id'])) if int(c['company_id']) in (4,78,24) else 99)
                    return company_rows, levels, 'supabase-live', None
                raise RuntimeError('Company skill data was incomplete for one or more companies')
            raise RuntimeError('No accessible company/skill rows were returned')
        except Exception as exc:
            return COMPANIES, DEMO_LEVELS, 'demo-snapshot', f'Live Supabase read unavailable: {type(exc).__name__}. Showing the saved Bootcamp2 snapshot.'
    return COMPANIES, DEMO_LEVELS, 'demo-snapshot', 'Supabase is not configured. Showing the saved Bootcamp2 snapshot.'


class CandidateSkill(BaseModel):
    model_config = ConfigDict(extra='allow')
    skill_name: str | None = None
    category_code: str | None = None
    # The brief does not define a numeric proficiency field. When supplied by
    # Profile Builder, accept 0 (unassessed) through 10; never infer a level.
    level: int | None = Field(default=None, ge=0, le=10)
    candidate_level: int | None = Field(default=None, ge=0, le=10)
    evidence: str | None = None
    confidence: str | None = None

class Candidate(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str = 'Candidate'
    email: str | None = None
    education: str | None = None
    role: str | None = None
    skills: list[CandidateSkill] = Field(default_factory=list)
    hackathons: list[Any] = Field(default_factory=list)
    internships: list[Any] = Field(default_factory=list)
    certifications: list[Any] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    cv_file: str | None = None

class CheckRequest(BaseModel):
    model_config = ConfigDict(extra='allow')
    candidate: Candidate | None = None
    profile: Candidate | None = None
    company_id: int

    def resolved_candidate(self) -> Candidate:
        candidate = self.candidate or self.profile
        if candidate is None:
            raise HTTPException(status_code=422, detail='Provide candidate or profile using the shared Profile Builder JSON contract.')
        return candidate


def normalize_candidate_skills(candidate: Candidate) -> dict[str, CandidateSkill]:
    by_code = {s['code']: s for s in SKILLS}
    by_name = {s['name'].casefold(): s for s in SKILLS}
    result: dict[str, CandidateSkill] = {}
    for item in candidate.skills:
        meta = by_code.get((item.category_code or '').upper()) or by_name.get((item.skill_name or '').casefold())
        if not meta:
            continue
        result[meta['code']] = item
    return result


def calculate(candidate: Candidate, company_id: int, company_rows: list[dict[str, Any]], levels: dict[int, list[int]]) -> dict[str, Any]:
    company = next((c for c in company_rows if int(c['company_id']) == company_id), None)
    if not company or company_id not in levels:
        raise HTTPException(status_code=404, detail='Company not found in the current skillset snapshot.')
    candidate_skills = normalize_candidate_skills(candidate)
    breakdown = []
    for index, skill in enumerate(SKILLS):
        entry = candidate_skills.get(skill['code'])
        candidate_level = int((entry.level if entry and entry.level is not None else entry.candidate_level) if entry and (entry.level is not None or entry.candidate_level is not None) else 0)
        required = int(levels[company_id][index])
        score = round(min(candidate_level / required, 1) * 100, 1) if candidate_level > 0 and required > 0 else 0.0
        gap = max(required - candidate_level, 0)
        breakdown.append({
            'skill_name': skill['name'], 'category_code': skill['code'],
            'required_level': required, 'candidate_level': candidate_level,
            'skill_score': score, 'gap': gap > 0, 'gap_amount': gap, 'gap_detected': gap > 0,
            'evidence': (entry.evidence if entry else None),
            'confidence': (entry.confidence if entry else None) or ('none' if candidate_level == 0 else 'self-reported'),
            'status': 'Missing data' if candidate_level == 0 else ('Meets bar' if gap == 0 else ('Close gap' if gap <= 2 else 'Priority gap')),
        })
    readiness = round(sum(x['skill_score'] for x in breakdown) / len(breakdown), 1)
    gaps = sorted([x for x in breakdown if x['gap_detected']], key=lambda x: (-x['gap_amount'], x['skill_score']))
    roadmap = []
    for idx, item in enumerate(gaps[:4], 1):
        action = {
          'COD':'Build one small project in a language used confidently; practise clean functions and debugging.',
          'DSA':'Solve 3–5 problems per topic and explain time/space complexity aloud.',
          'APTI':'Practise timed quantitative and logical reasoning sets; review errors weekly.',
          'COMM':'Prepare a 90-second project explanation and practise structured STAR answers.',
          'OOD':'Model a small system with classes, interfaces, composition, and unit tests.',
          'AI':'Build a small AI feature and document evaluation, limitations, and failure cases.',
          'SQL':'Practise joins, aggregation, subqueries, indexes, and schema design on a sample dataset.',
          'SYSD':'Draw a simple architecture and explain API, data, caching, and failure trade-offs.',
          'CLOUD':'Deploy a small app and practise environment variables, logs, and basic CI.',
          'SWE':'Add tests, Git workflow, code review notes, and clear project documentation.',
          'NETW':'Review TCP/IP, HTTP, DNS, TLS, and use basic network troubleshooting tools.',
          'OS':'Revise processes, threads, scheduling, memory, deadlocks, and synchronization.',
        }.get(item['category_code'], 'Review fundamentals and demonstrate the skill in a small practical task.')
        roadmap.append({'priority': idx, 'skill_name': item['skill_name'], 'gap': item['gap_amount'], 'action': action})
    return {
      'candidate_name': candidate.name, 'company': company.get('short_name') or company.get('name'),
      'company_id': company_id, 'readiness_score': readiness,
      'readiness_label': 'Strong alignment' if readiness >= 80 else ('Building alignment' if readiness >= 60 else 'Significant gaps'),
      'skillset_gap': breakdown, 'priority_gaps': gaps[:4], 'roadmap': roadmap,
      'skills_assessed': sum(1 for x in breakdown if x['candidate_level'] > 0),
      'skills_total': len(SKILLS),
      'methodology': 'Unweighted mean of min(candidate level / required level, 1) across 12 categories. Missing candidate levels score 0.',
      'disclaimer': 'This is a competency-alignment estimate, not a hiring probability. Candidate levels are self-reported unless supported by upstream evidence.',
    }

@app.get('/api/health')
def health():
    companies, levels, mode, warning = company_and_levels()
    return {'status':'ok','service':'RADIX Talent Check','data_mode':mode,'warning':warning,'companies_available':len(companies),'skills_available':len(SKILLS)}

@app.get('/api/companies')
def get_companies():
    companies, levels, mode, warning = company_and_levels()
    return {'companies':[{'company_id':int(c['company_id']),'name':c.get('name') or c.get('short_name'),'short_name':c.get('short_name') or c.get('name')} for c in companies], 'skills':SKILLS, 'data_mode':mode, 'warning':warning}

@app.post('/api/talent-check')
def talent_check(request: CheckRequest):
    companies, levels, mode, warning = company_and_levels()
    result = calculate(request.resolved_candidate(), request.company_id, companies, levels)
    result.update({'data_mode':mode,'data_warning':warning})
    return result

@app.post('/api/profile/talent-check')
def talent_check_profile_contract(request: CheckRequest):
    """Alias for integrations that prefer a profile-oriented endpoint."""
    return talent_check(request)

@app.post('/api/compare')
def compare(request: Candidate):
    companies, levels, mode, warning = company_and_levels()
    results = [calculate(request, int(c['company_id']), companies, levels) for c in companies if int(c['company_id']) in (4,78,24)]
    return {'results':sorted(results, key=lambda r:r['readiness_score'], reverse=True),'data_mode':mode,'warning':warning}
