"""Role 4 Talent Check over HTTP (needs fastapi/httpx; see requirements-dev.txt). Phase 5."""
import pytest
from fastapi.testclient import TestClient
from app import app
from radix_jd.contract import TalentCheckResult, RADIX_CATEGORY_CODES

client = TestClient(app)


def check(skills, company_id=4):
    r = client.post("/api/talent-check", json={"profile": {"name": "T", "skills": skills}, "company_id": company_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_result_validates_against_official_contract_even_when_nothing_assessed():
    TalentCheckResult.model_validate(check([]))
    TalentCheckResult.model_validate(check([{"skill_name": "Python", "category_code": "COD", "level": 7}]))


def test_contract_and_extension_keys_present():
    r = check([{"skill_name": "Python", "category_code": "COD", "level": 4}])
    cod = next(x for x in r["skillset_gap"] if x["category_code"] == "COD")
    assert {"category_code", "required_level", "candidate_level", "gap", "gap_detected", "gap_amount", "status", "explanation"} <= set(cod)
    assert cod["required_level"] == 8 and cod["candidate_level"] == 4 and cod["gap"] is True and cod["gap_amount"] == 4
    assert r["readiness_score"] == 50.0 and r["company"] == "Google"


def test_legacy_level_zero_from_old_clients_is_unassessed():
    r = check([{"skill_name": "Python", "category_code": "COD", "level": 0}])
    assert r["readiness_score"] is None and r["skills_assessed"] == 0


def test_several_skills_in_a_category_use_the_best_level_in_any_order():
    a = [{"skill_name": "Java", "category_code": "COD"}, {"skill_name": "Python", "category_code": "COD", "level": 8}]
    assert check(a)["readiness_score"] == check(list(reversed(a)))["readiness_score"] == 100.0


def test_different_candidates_and_companies_give_different_results():
    strong = [{"skill_name": c, "category_code": c, "level": 9} for c in sorted(RADIX_CATEGORY_CODES)]
    weak = [{"skill_name": c, "category_code": c, "level": 4} for c in sorted(RADIX_CATEGORY_CODES)]
    assert check(strong, 4)["readiness_score"] > check(weak, 4)["readiness_score"]
    assert check(weak, 24)["readiness_score"] > check(weak, 4)["readiness_score"]   # Oracle bar is lower than Google


def test_unknown_company_is_404():
    assert client.post("/api/talent-check", json={"profile": {"skills": []}, "company_id": 999}).status_code == 404


def test_invalid_level_is_rejected_not_clamped():
    r = client.post("/api/talent-check", json={"profile": {"skills": [{"skill_name": "x", "category_code": "COD", "level": 11}]}, "company_id": 4})
    assert r.status_code == 422


def test_snapshot_result_is_saved_with_company_ref(monkeypatch):
    import app as module
    sent = {}
    monkeypatch.setattr(module.STORE, "url", "https://x.example")
    monkeypatch.setattr(module.STORE, "key", "k")
    monkeypatch.setattr(module.STORE, "insert_result", lambda table, payload: sent.update(table=table, **payload) or {"saved": True, "mode": "supabase", "id": "r1"})
    check([], 78)
    assert sent["table"] == "radix_talent_check_results" and sent["company_ref"] == "snapshot:78" and sent["company_id"] == 78
