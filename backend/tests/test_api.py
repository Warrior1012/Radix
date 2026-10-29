from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_health_and_companies():
    assert client.get('/api/health').status_code == 200
    assert len(client.get('/api/companies').json()) == 3

def test_skill_match_scores_and_aliases():
    payload = {
      'profile': {'name':'Test Candidate','skills':[{'skill_name':'Python','category_code':'COD'},{'skill_name':'JS','category_code':'COD'}]},
      'job': {'job_id':'demo-1','required_skills':['Python','JavaScript','SQL'],'preferred_skills':['Docker']}
    }
    result = client.post('/api/skill-match', json=payload)
    assert result.status_code == 200
    data = result.json()
    assert data['match_score'] == 57.14
    assert data['matched_required_skills'] == ['Python','JavaScript']
    assert data['missing_required_skills'] == ['SQL']

def test_talent_check_missing_levels_are_not_inferred():
    payload={'profile':{'name':'Test Candidate','skills':[{'skill_name':'Python','category_code':'COD','evidence':'Python project','confidence':'high'}]},'company_id':78}
    data=client.post('/api/talent-check',json=payload).json()
    assert data['skills_total'] == 12
    assert data['skills_assessed'] == 0
    assert data['readiness_score'] is None  # Phase 5 (D5a): unassessed is not zero ability
    assert data['skills_assessed'] == 0 and data['readiness_floor'] == 0

def test_profile_save_and_load():
    payload={'name':'Test Candidate','email':'test@example.com','skills':[]}
    saved=client.post('/api/profile',json=payload)
    assert saved.status_code == 200
    candidate_id=saved.json()['profile']['candidate_id']
    loaded=client.get('/api/profile/'+candidate_id)
    assert loaded.status_code == 200
    assert loaded.json()['email']=='test@example.com'

def test_company_benchmark_category_order_matches_role4_snapshot():
    from app import CATEGORIES, COMPANIES
    assert [code for code, _ in CATEGORIES] == [
        'COD', 'DSA', 'APTI', 'COMM', 'OOD', 'AI', 'SQL', 'SYSD', 'CLOUD', 'SWE', 'NETW', 'OS'
    ]
    google = next(c for c in COMPANIES if c['company_id'] == 4)
    assert google['levels'] == [8, 9, 9, 7, 8, 7, 8, 4, 9, 9, 9, 9]

def test_talent_check_returns_all_shared_categories_in_correct_order():
    from app import CATEGORIES
    payload = {'profile': {'name':'Order Test','skills':[]}, 'company_id':4}
    response = client.post('/api/talent-check', json=payload)
    assert response.status_code == 200
    rows = response.json()['skillset_gap']
    assert [row['category_code'] for row in rows] == [code for code, _ in CATEGORIES]
    assert rows[2]['required_level'] == 9  # Aptitude, not OOD
    assert rows[4]['required_level'] == 8  # OOD

def test_profile_builder_lists_and_projects_survive_save_load():
    payload = {
      'name':'Profile Test', 'skills':[], 'hackathons':['Hackathon A'],
      'internships':['Backend Intern'], 'experience':['Software Engineer at Acme'], 'certifications':['Cloud Basics'],
      'preferred_roles':['Software Engineer'], 'projects':['RADIX demo']
    }
    saved = client.post('/api/profile', json=payload)
    assert saved.status_code == 200
    candidate_id = saved.json()['profile']['candidate_id']
    loaded = client.get('/api/profile/'+candidate_id).json()
    assert loaded['hackathons'] == ['Hackathon A']
    assert loaded['internships'] == ['Backend Intern']
    assert loaded['experience'] == ['Software Engineer at Acme']
    assert loaded['certifications'] == ['Cloud Basics']
    assert loaded['preferred_roles'] == ['Software Engineer']
    assert loaded['projects'] == ['RADIX demo']


def test_skill_matching_canonicalizes_role5_aliases():
    payload = {
      'profile': {'name':'Alias Test','skills':[{'skill_name':'Amazon Web Services','category_code':'CLOUD'},{'skill_name':'React.js','category_code':'COD'}]},
      'job': {'required_skills':['AWS','React'],'preferred_skills':[]}
    }
    data = client.post('/api/skill-match', json=payload).json()
    assert data['match_score'] == 100.0
    assert data['matched_required_skills'] == ['AWS', 'React']

def test_resume_skill_category_does_not_misclassify_tailwind_as_ai():
    from app import skill_category
    assert skill_category('Tailwind CSS') == 'COD'
    assert skill_category('Machine Learning') == 'AI'
    assert skill_category('PostgreSQL') == 'SQL'

def _docx_bytes(text: str) -> bytes:
    from docx import Document
    from io import BytesIO
    d = Document()
    d.add_paragraph(text)
    stream = BytesIO()
    d.save(stream)
    return stream.getvalue()

def test_jd_analytics_upload_contract(monkeypatch):
    import app as module
    async def fake_extract(text):
        return {'company':'Acme','role':'Backend Engineer','skills':[
          {'skill_name':'Python','category_code':'COD','evidence':'Python is required','confidence':'high'},
          {'skill_name':'Docker','category_code':'CLOUD','evidence':'Docker is preferred','confidence':'medium'}
        ],'extraction_method':'llm_test','analysis_meta':{}}
    monkeypatch.setattr(module, 'extract_with_llm', fake_extract)
    response = client.post('/api/analyze-jd', files={'file':('jd.docx',_docx_bytes('Acme is hiring a Backend Engineer. Python is required. Docker is preferred for deployment.'))})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['source_type'] == 'jd'
    assert data['required_skills'] == ['Python']
    assert data['preferred_skills'] == ['Docker']
    assert {'skill_name','category_code','evidence','confidence'} <= set(data['skills'][0])

def test_resume_parsing_upload_contract(monkeypatch):
    import app as module
    async def fake_parse(text):
        return {'name':'A Candidate','email':'a@example.com','education':'B.Tech CSE',
          'skills':[{'skill_name':'Python','category_code':'COD','evidence':'Built a Python app','confidence':'high'}],
          'projects':['Python app'], 'experience':['Software intern'], 'certifications':['Cloud Basics']}
    monkeypatch.setattr(module, 'parse_resume_llm', fake_parse)
    response = client.post('/api/parse-resume', files={'file':('resume.docx',_docx_bytes('A Candidate\na@example.com\nB.Tech CSE\nBuilt a Python app as a software intern.'))})
    assert response.status_code == 200, response.text
    profile = response.json()['profile']
    assert profile['name'] == 'A Candidate'
    assert profile['education'] == 'B.Tech CSE'
    assert profile['skills'][0]['category_code'] == 'COD'
    assert profile['projects'] == ['Python app']
    assert profile['experience'] == ['Software intern']
    assert profile['internships'] == []

def test_end_to_end_profile_talent_and_job_match_flow():
    saved = client.post('/api/profile', json={
      'name':'E2E Candidate','skills':[{'skill_name':'Python','category_code':'COD','evidence':'Built Python apps','confidence':'high','level':8}],
      'hackathons':['Hackathon X'],'projects':['Python API']
    })
    assert saved.status_code == 200
    profile = saved.json()['profile']
    check = client.post('/api/talent-check', json={'profile':profile,'company_id':78})
    assert check.status_code == 200
    assert len(check.json()['skillset_gap']) == 12
    match = client.post('/api/skill-match', json={'profile':profile,'job':{'job_id':'jd-e2e','required_skills':['Python','SQL'],'preferred_skills':['Docker']}})
    assert match.status_code == 200
    assert match.json()['matched_required_skills'] == ['Python']
    assert match.json()['missing_required_skills'] == ['SQL']


def test_integrations_status_does_not_expose_secrets(monkeypatch):
    import app as module
    monkeypatch.setattr(module.STORE, 'url', '')
    monkeypatch.setattr(module.STORE, 'key', '')
    response = client.get('/api/integrations/status')
    assert response.status_code == 200
    data = response.json()
    assert data['ai']['configured'] is False
    assert data['supabase']['configured'] is False
    assert data['secrets_exposed'] is False
    assert 'GEMINI_API_KEY=' not in response.text

def test_resume_parsing_does_not_silently_fallback_when_disabled(monkeypatch):
    import app as module
    async def no_ai(text): return None
    monkeypatch.setattr(module, 'parse_resume_llm', no_ai)
    monkeypatch.setenv('DEMO_FALLBACK', 'false')
    response = client.post('/api/parse-resume', files={'file':('resume.docx',_docx_bytes('A Candidate\n' + 'Python backend engineer with projects and education. ' * 4))})
    assert response.status_code == 502
    assert 'No keyword fallback was used' in response.json()['detail']


def test_supabase_company_benchmarks_are_exposed_as_distinct_source(monkeypatch):
    import app as module
    levels = {'COD':5,'DSA':6,'APTI':6,'COMM':6,'OOD':6,'AI':6,'SQL':6,'SYSD':5,'CLOUD':5,'SWE':7,'NETW':5,'OS':5}
    monkeypatch.setattr(module.STORE, 'url', 'https://example.supabase.co')
    monkeypatch.setattr(module.STORE, 'key', 'test-key')
    monkeypatch.setattr(module.STORE, 'list_company_benchmarks', lambda: [{
        'company_id': 9001, 'name':'Example DB Company', 'short_name':'Example DB Company',
        'skill_levels': levels, 'levels':[levels[c] for c,_ in module.CATEGORIES], 'source':'supabase'
    }])
    monkeypatch.setattr(module.STORE, 'insert_result', lambda table, payload: {'saved':True,'mode':'supabase','id':'test-result'})
    rows = client.get('/api/companies').json()
    db_company = next(x for x in rows if x['company_id'] == 'supabase:9001')
    assert db_company['source'] == 'supabase'
    response = client.post('/api/talent-check', json={'profile': {'name':'DB Candidate','skills':[]}, 'company_id':'supabase:9001'})
    assert response.status_code == 200, response.text
    assert response.json()['benchmark_source'] == 'supabase'
    assert response.json()['skillset_gap'][0]['required_level'] == 5

def test_supabase_skillset_name_mapping_prioritizes_specific_categories():
    from radix_jd.supabase_store import SupabaseStore
    assert SupabaseStore._category_code('OOD', 'Object-Oriented Programming and Design') == 'OOD'
    assert SupabaseStore._category_code('AI', 'AI Native Engineering') == 'AI'
    assert SupabaseStore._category_code('COD', 'Coding') == 'COD'


def test_jd_content_cache_and_stats_use_actual_analysis(monkeypatch):
    import app as module
    calls = {"count": 0}

    monkeypatch.setattr(module, "configured_targets", lambda: [{"provider": "gemini", "model": "test-model", "base_url": "https://example.test", "api_key": "test-only"}])

    async def fake_extract(text):
        calls["count"] += 1
        return {
            "company": "Acme", "role": "Backend Engineer",
            "skills": [
                {"skill_name": "Python", "category_code": "COD", "evidence": "Python is required for this job.", "confidence": "high", "requirement_type": "required"},
                {"skill_name": "PostgreSQL", "category_code": "SQL", "evidence": "PostgreSQL is preferred for this job.", "confidence": "medium", "requirement_type": "preferred"},
            ],
            "extraction_method": "llm_test",
            "analysis_meta": {"models_invoked": ["gemini:test-model"]},
        }

    monkeypatch.setattr(module, "extract_with_llm", fake_extract)
    text = "Acme is hiring a Backend Engineer. Python is required for this job. PostgreSQL is preferred for this job. " * 2
    first = client.post('/api/analyze-jd', files={'file': ('cache-test.docx', _docx_bytes(text))})
    second = client.post('/api/analyze-jd', files={'file': ('cache-test.docx', _docx_bytes(text))})
    assert first.status_code == 200 and second.status_code == 200
    assert calls["count"] == 1
    assert first.json()["analysis_meta"]["cache_hit"] is False
    assert second.json()["analysis_meta"]["cache_hit"] is True
    assert second.json()["analysis_meta"]["model_calls"] == 0

    stats = client.get('/api/jd/stats/' + second.json()['jd_id'])
    assert stats.status_code == 200
    data = stats.json()
    assert data['total_skills'] == 2
    assert data['required'] == 1 and data['preferred'] == 1
    assert data['category_counts'] == {'COD': 1, 'SQL': 1}


def test_eval_latest_never_manufactures_metrics_without_a_report():
    response = client.get('/api/eval/latest')
    assert response.status_code == 200
    data = response.json()
    if not data.get('available'):
        assert data['status'] == 'not_run' and data['metrics'] is None
        assert 'ground truth' in data['message']
