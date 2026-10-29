"""HTTP-level regression tests for the additive Decision Lab endpoints."""
from fastapi.testclient import TestClient

import app as module
from app import app

client = TestClient(app)

PROFILE = {
    "name": "Demo Candidate",
    "skills": [
        {"skill_name": "Python", "category_code": "COD", "evidence": "Built a Python API", "confidence": "high", "level": None}
    ],
}
JOB = {
    "job_id": "decision-lab-test",
    "role": "Junior Python Backend Engineer",
    "required_skills": ["Python", "FastAPI"],
    "preferred_skills": [],
    "skills": [
        {"skill_name": "Python", "category_code": "COD", "requirement_type": "required"},
        {"skill_name": "FastAPI", "category_code": "SWE", "requirement_type": "required"},
    ],
}


def test_proofgraph_endpoint_returns_requirement_status_without_storage(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Decision Lab must not persist or fetch saved profile/results")

    monkeypatch.setattr(module.PROFILE_REPO, "get", forbidden)
    monkeypatch.setattr(module.PROFILE_REPO, "save", forbidden)
    monkeypatch.setattr(module.STORE, "insert_result", forbidden)

    response = client.post("/api/decision-lab/proofgraph", json={"profile": PROFILE, "job": JOB})
    assert response.status_code == 200, response.text
    result = response.json()
    by_skill = {item["skill"]: item for item in result["requirements"]}
    assert result["profile_saved"] is False
    assert by_skill["Python"]["status"] == "evidence_available"
    assert by_skill["FastAPI"]["status"] == "unassessed"


def test_simulator_is_hypothetical_and_returns_delta_without_storage(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Decision Lab must not persist hypothetical changes")

    monkeypatch.setattr(module.PROFILE_REPO, "save", forbidden)
    monkeypatch.setattr(module.STORE, "insert_result", forbidden)

    response = client.post(
        "/api/decision-lab/simulate",
        json={"profile": PROFILE, "job": JOB, "assumed_skills": ["FastAPI"]},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["hypothetical"] is True
    assert result["persisted"] is False
    assert result["baseline_score"] == 50.0
    assert result["scenario_score"] == 100.0
    assert result["score_delta"] == 50.0
    assert result["assumed_skills"] == ["FastAPI"]
    assert "not created or changed" in result["assumption_note"]


def test_simulator_rejects_non_missing_or_arbitrary_skill():
    response = client.post(
        "/api/decision-lab/simulate",
        json={"profile": PROFILE, "job": JOB, "assumed_skills": ["Go"]},
    )
    assert response.status_code == 422
