"""Offline tests for the read-only AI Profile Builder review endpoint."""
from fastapi.testclient import TestClient
from app import app
import radix_jd.profile_review as review_module
from radix_jd.gemini import LLMError

client = TestClient(app)
VALID_REVIEW = {
    "summary": "The profile includes concrete backend project evidence; add more detail where work is currently brief.",
    "strengths": ["The Student Task API description names the core technologies."],
    "profile_gaps": [{
        "area": "projects", "priority": "medium",
        "issue": "The project does not state a testing outcome.",
        "recommendation": "Add the types of tests run and a verifiable result, if available."
    }],
    "skill_reviews": [{
        "skill_name": "Python", "status": "evidence_present",
        "observation": "The evidence refers to an academic project.",
        "next_step": "Link the project repository or describe the part you implemented."
    }, {
        "skill_name": "FastAPI", "status": "evidence_present",
        "observation": "Evidence mentions a REST API built using FastAPI.",
        "next_step": "Add a short example endpoint or test that demonstrates this work."
    }, {
        "skill_name": "Imaginary Skill", "status": "evidence_present",
        "observation": "Not actually supplied.",
        "next_step": "This should be filtered out."
    }],
    "limitations": ["The review uses only the fields provided and does not verify external links."],
}


def body(profile=None):
    return profile or {
        "name": "Candidate Name Must Not Be Sent",
        "email": "private-not-sent@example.com",
        "candidate_id": "private-id-123",
        "cv_file": "private-resume-name.pdf",
        "education": "B.Tech Computer Science",
        "skills": [
            {"skill_name": "Python", "category_code": "COD", "level": 1, "evidence": "Built academic projects using Python", "confidence": "high"},
            {"skill_name": "FastAPI", "category_code": "COD", "level": None, "evidence": "Built a REST API in Python using FastAPI", "confidence": "high"},
        ],
        "projects": ["Student Task API: Built a REST API using Python and FastAPI."],
    }


def test_empty_profile_returns_needs_data_without_provider(monkeypatch):
    monkeypatch.setattr(review_module, "configured_targets", lambda: [])
    response = client.post("/api/profile-review", json={})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "needs_data"


def test_no_configured_provider_returns_graceful_status_without_changing_profile(monkeypatch):
    monkeypatch.setattr(review_module, "configured_targets", lambda: [])
    profile = body()
    original = profile.copy()
    response = client.post("/api/profile-review", json=profile)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unavailable"
    assert profile == original


def test_provider_fallback_filters_invented_skill_and_does_not_send_identity(monkeypatch):
    targets = [
        {"provider": "gemini", "model": "bad-model", "base_url": "https://example.invalid", "api_key": "fake"},
        {"provider": "groq", "model": "good-model", "base_url": "https://example.invalid", "api_key": "fake"},
    ]
    monkeypatch.setattr(review_module, "configured_targets", lambda: targets)
    seen = []
    async def fake_call_json(client, target, **kwargs):
        seen.append(target["provider"])
        assert "private-not-sent@example.com" not in kwargs["user"]
        assert "private-id-123" not in kwargs["user"]
        assert "private-resume-name.pdf" not in kwargs["user"]
        if target["provider"] == "gemini":
            raise LLMError("rate_limited", "synthetic fail", model=target["model"], provider=target["provider"])
        return VALID_REVIEW
    monkeypatch.setattr(review_module, "call_json", fake_call_json)
    response = client.post("/api/profile-review", json=body())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ready"
    assert data["ai_assist"]["provider_used"] == "groq"
    assert data["ai_assist"]["fallback_used"] is True
    assert seen == ["gemini", "groq"]
    assert [x["skill_name"] for x in data["review"]["skill_reviews"]] == ["Python", "FastAPI"]
    fastapi = next(x for x in data["review"]["skill_reviews"] if x["skill_name"] == "FastAPI")
    assert fastapi["status"] == "proficiency_unassessed"


def test_review_does_not_write_to_profile_store(monkeypatch, tmp_path):
    monkeypatch.setattr(review_module, "configured_targets", lambda: [])
    response = client.post("/api/profile-review", json=body())
    assert response.status_code == 200
    assert not list(tmp_path.rglob("*.json"))
