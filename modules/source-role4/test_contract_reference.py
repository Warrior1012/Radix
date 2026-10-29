from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as module

client = TestClient(module.app)


def mock_data():
    return module.COMPANIES, module.DEMO_LEVELS, 'demo-snapshot', 'Using test snapshot'


def test_health_and_company_contract(monkeypatch):
    monkeypatch.setattr(module, 'company_and_levels', mock_data)
    health = client.get('/api/health')
    assert health.status_code == 200
    data = client.get('/api/companies').json()
    assert len(data['skills']) == 12
    assert {x['code'] for x in data['skills']} == {'COD','DSA','APTI','COMM','OOD','AI','SQL','SYSD','CLOUD','SWE','NETW','OS'}


def test_profile_contract_accepts_canonical_skills_and_boolean_gap(monkeypatch):
    monkeypatch.setattr(module, 'company_and_levels', mock_data)
    profile = {
        'name': 'Contract Test', 'email': 'test@example.com', 'education': 'B.Tech',
        'role': 'SWE Intern', 'hackathons': [], 'internships': [], 'certifications': [],
        'preferred_roles': ['SWE Intern'], 'cv_file': '',
        'skills': [
            {'skill_name': 'Data Structures and Algorithms', 'category_code': 'DSA', 'evidence': 'Practised graphs', 'confidence': 'medium', 'level': 6},
            {'skill_name': 'Unassessed OS', 'category_code': 'OS', 'evidence': 'Not evaluated', 'confidence': 'low'}
        ]
    }
    response = client.post('/api/talent-check', json={'candidate': profile, 'company_id': 4})
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result['skillset_gap']) == 12
    dsa = next(x for x in result['skillset_gap'] if x['category_code'] == 'DSA')
    assert dsa['candidate_level'] == 6 and dsa['required_level'] == 9
    assert dsa['gap'] is True and dsa['gap_amount'] == 3
    os_row = next(x for x in result['skillset_gap'] if x['category_code'] == 'OS')
    assert os_row['candidate_level'] == 0 and os_row['gap'] is True


def test_profile_alias_and_compare(monkeypatch):
    monkeypatch.setattr(module, 'company_and_levels', mock_data)
    body = {'profile': {'name': 'Alias', 'skills': [{'category_code':'COD','skill_name':'Coding','level':8}]}, 'company_id': 4}
    response = client.post('/api/profile/talent-check', json=body)
    assert response.status_code == 200, response.text
    compare = client.post('/api/compare', json={'name':'Alias','skills':[{'category_code':'COD','skill_name':'Coding','level':8}]})
    assert compare.status_code == 200
    assert len(compare.json()['results']) == 3
