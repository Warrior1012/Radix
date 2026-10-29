"""Role 5 Skill Matching over HTTP (needs fastapi/httpx; see requirements-dev.txt). Phase 6."""
import pytest
from fastapi.testclient import TestClient
import app as module
from app import app
from radix_jd.contract import SkillMatchResult

client = TestClient(app)
PROFILE = {"name": "M", "skills": [{"skill_name": "Python", "category_code": "COD"}, {"skill_name": "js", "category_code": "COD"}]}


def match(**body):
    return client.post("/api/skill-match", json={"profile": PROFILE, **body})


def test_response_validates_against_official_contract_and_keeps_extensions():
    r = match(job={"job_id": "x", "source_file": "g.pdf", "required_skills": ["Python", "SQL"], "preferred_skills": ["JavaScript"]})
    assert r.status_code == 200, r.text
    SkillMatchResult.model_validate(r.json())
    d = r.json()
    assert d["jd_source_file"] == "g.pdf" and d["matched_skills"] == ["Python", "JavaScript"] and d["missing_skills"] == ["SQL"]
    assert d["matched_required_skills"] == ["Python"] and d["gaps"][0]["points_lost"] == 2 and d["jd_resolution"] == "request"


def test_unable_to_calculate_still_validates_contract():
    r = match(job={"required_skills": []})
    assert r.status_code == 200 and r.json()["match_score"] is None
    SkillMatchResult.model_validate(r.json())


def test_neither_job_nor_jd_id_is_422():
    assert match().status_code == 422


def test_jd_id_unknown_is_404_and_bad_id_is_400():
    assert match(jd_id="does-not-exist").status_code == 404
    assert match(jd_id="../etc").status_code == 400


def test_jd_id_resolves_the_stored_analysed_jd_and_survives_cache_loss(monkeypatch):
    jd = {"jd_id": "jd-test-1", "source_file": "oracle.pdf", "company": "Oracle", "role": "SWE", "skills": [
        {"skill_name": "Python", "requirement_type": "required"}, {"skill_name": "SQL", "requirement_type": "required"}],
        "required_skills": ["Python", "SQL"], "preferred_skills": []}
    module.JD_STORE.save(jd)
    module.JDS.clear()                                  # simulate a restart: no in-process cache
    d = match(jd_id="jd-test-1").json()
    assert d["jd_resolution"] == "jd_id" and d["jd_source_file"] == "oracle.pdf" and d["job_id"] == "jd-test-1"
    assert d["match_score"] == 50.0 and d["missing_skills"] == ["SQL"]


def test_stored_jd_wins_over_client_sent_lists(monkeypatch):
    module.JD_STORE.save({"jd_id": "jd-test-2", "required_skills": ["SQL"], "preferred_skills": [], "skills": []})
    d = match(jd_id="jd-test-2", job={"required_skills": ["Python"]}).json()
    assert d["missing_skills"] == ["SQL"] and d["jd_resolution"] == "jd_id"


def test_unknown_jd_id_with_request_lists_is_labelled():
    d = match(jd_id="gone", job={"required_skills": ["Python"]}).json()
    assert d["jd_resolution"] == "jd_id_not_found_used_request_lists" and d["match_score"] == 100.0


def test_jd_id_falls_back_to_supabase_row(monkeypatch):
    monkeypatch.setattr(module.STORE, "url", "https://x.example"); monkeypatch.setattr(module.STORE, "key", "k")
    monkeypatch.setattr(module.STORE, "get_jd_result", lambda i: {"id": i, "source_file": "db.pdf", "skills": [
        {"skill_name": "Python"}, {"skill_name": "Docker", "requirement_type": "preferred"}]})
    monkeypatch.setattr(module.STORE, "insert_result", lambda t, p: {"saved": True, "mode": "supabase", "id": "r"})
    d = match(jd_id="row-1").json()
    assert d["jd_source_file"] == "db.pdf" and d["match_score"] == 66.67 and d["missing_preferred_skills"] == ["Docker"]


def test_different_candidates_get_visibly_different_results():
    job = {"required_skills": ["Python", "SQL", "Docker"], "preferred_skills": ["AWS"]}
    strong = {"name": "S", "skills": [{"skill_name": n} for n in ("Python", "SQL", "Docker", "AWS")]}
    weak = {"name": "W", "skills": [{"skill_name": "Python"}]}
    a = client.post("/api/skill-match", json={"profile": strong, "job": job}).json()["match_score"]
    b = client.post("/api/skill-match", json={"profile": weak, "job": job}).json()["match_score"]
    assert a == 100.0 and b == 28.57


def test_semantic_match_api_uses_only_prevalidated_candidate_skill_labels(monkeypatch):
    async def fake_semantic(candidate_skills, job, unmatched):
        assert "FastAPI framework service implementation" in unmatched
        return {module.canonical("FastAPI framework service implementation"): "FastAPI"}, {
            "enabled": True, "applied": True, "fallback_used": False,
            "provider_used": "groq", "model_used": "test-model",
            "semantic_matches": [{"jd_skill": "FastAPI framework service implementation", "candidate_skill": "FastAPI", "reason": "Resume evidence shows FastAPI REST API development."}],
        }

    monkeypatch.setattr(module, "suggest_semantic_matches", fake_semantic)
    profile = {"name": "M", "skills": [
        {"skill_name": "FastAPI", "category_code": "COD", "evidence": "Built a REST API using FastAPI"},
    ]}
    job = {
        "job_id": "sem-j1",
        "required_skills": ["FastAPI framework service implementation"],
        "preferred_skills": [],
        "skills": [{"skill_name": "FastAPI framework service implementation", "category_code": "COD", "requirement_type": "required", "evidence": "FastAPI framework service implementation is required"}],
    }
    response = client.post("/api/skill-match", json={"profile": profile, "job": job})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["match_score"] == 90.0  # semantic match receives 90% of the requirement weight
    assert data["match_details"][0]["points_earned"] == 1.8
    assert data["matched_required_skills"] == ["FastAPI framework service implementation"]
    assert data["match_details"][0]["match_type"] == "semantic_ai"
    assert data["exact_only_score"] == 0.0
    assert data["ai_assist"]["provider_used"] == "groq"
