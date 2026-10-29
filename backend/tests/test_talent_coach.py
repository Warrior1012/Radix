"""Offline tests for optional, evidence-grounded Talent Check AI coaching."""
from fastapi.testclient import TestClient
import app as app_module
from app import app
import radix_jd.talent_coach as coach_module
from radix_jd.gemini import LLMError

client = TestClient(app)

VALID_COACHING = {
    "ai_rating_10": 6.8,
    "rating_rationale": "The assessed categories are moderately close to the benchmark; only one category is scored, so this is low confidence.",
    "rating_confidence": "high",
    "rating_evidence": ["Coding level 5 is assessed against the company benchmark."],
    "summary": "Use the current benchmark gaps to guide practice; the official score is unchanged.",
    "strengths": ["The profile has an assessed Coding level."],
    "priorities": [{
        "category_code": "COD",
        "priority": "high",
        "action": "Build a small Python service and review it against the benchmark.",
        "practice_task": "Implement a validated CRUD endpoint and add pytest coverage.",
        "evidence_to_add": "Add the repository and passing test results as project evidence.",
    }],
    "seven_day_plan": ["Day 1-2: implement one endpoint.", "Day 3-4: add tests."],
    "limitations": ["Only one category currently has a verified proficiency level."],
}


def request(skills=None, company_id=4):
    return client.post("/api/talent-coach", json={
        "profile": {
            "name": "Synthetic Candidate",
            "email": "private-not-sent@example.com",
            "skills": skills if skills is not None else [
                {"skill_name": "Python", "category_code": "COD", "level": 5,
                 "evidence": "Built an academic project using Python", "confidence": "high"}
            ],
            "projects": ["Built a small academic API"],
        },
        "company_id": company_id,
    })


def test_coaching_without_provider_falls_back_without_losing_score(monkeypatch):
    monkeypatch.setattr(coach_module, "configured_targets", lambda: [])
    response = request()
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["readiness_score"] == 62.5
    assert data["status"] == "unavailable"
    assert data["ai_assist"]["reason"] == "no_ai_provider_configured"


def test_no_assessed_skills_skips_llm_and_does_not_infer_proficiency(monkeypatch):
    monkeypatch.setattr(coach_module, "configured_targets", lambda: [{"provider": "groq", "model": "test-model", "base_url": "https://example.invalid", "api_key": "fake"}])
    async def forbidden_call(*args, **kwargs):
        raise AssertionError("LLM should not be called when no skills are assessed")
    monkeypatch.setattr(coach_module, "call_json", forbidden_call)
    response = request(skills=[{"skill_name": "Python", "category_code": "COD", "level": None, "evidence": "Built a script"}])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["readiness_score"] is None
    assert data["status"] == "needs_assessment"


def test_provider_fallback_returns_validated_coaching(monkeypatch):
    targets = [
        {"provider": "gemini", "model": "bad-model", "base_url": "https://example.invalid", "api_key": "fake"},
        {"provider": "groq", "model": "good-model", "base_url": "https://example.invalid", "api_key": "fake"},
    ]
    monkeypatch.setattr(coach_module, "configured_targets", lambda: targets)
    seen = []
    async def fake_call_json(client, target, **kwargs):
        seen.append(target["provider"])
        if target["provider"] == "gemini":
            raise LLMError("rate_limited", "synthetic failure", model=target["model"], provider=target["provider"])
        # Verify personal contact data isn't included in the prompt.
        assert "private-not-sent@example.com" not in kwargs["user"]
        return VALID_COACHING
    monkeypatch.setattr(coach_module, "call_json", fake_call_json)
    response = request()
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ready"
    assert data["readiness_score"] == 62.5
    assert data["ai_assist"]["provider_used"] == "groq"
    assert data["ai_assist"]["fallback_used"] is True
    assert seen == ["gemini", "groq"]
    assert data["coaching"]["priorities"][0]["category_code"] == "COD"
    # With just 1/12 assessed categories, server-side validation downgrades confidence.
    assert data["coaching"]["ai_rating_10"] == 6.8
    assert data["coaching"]["rating_confidence"] == "low"
    assert data["coaching"]["benchmark_anchor_10"] == 6.2


def test_model_cannot_add_unknown_categories_to_coaching(monkeypatch):
    target = {"provider": "groq", "model": "good-model", "base_url": "https://example.invalid", "api_key": "fake"}
    monkeypatch.setattr(coach_module, "configured_targets", lambda: [target])
    invalid = {**VALID_COACHING, "priorities": [{
        "category_code": "NOT_A_RADIX_CATEGORY", "priority": "high", "action": "Do something",
        "practice_task": "Practice", "evidence_to_add": "Add evidence"
    }]}
    async def fake_call_json(client, target, **kwargs):
        return invalid
    monkeypatch.setattr(coach_module, "call_json", fake_call_json)
    response = request()
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ready"
    assert data["coaching"]["priorities"] == []



def test_ai_rating_is_bounded_against_deterministic_benchmark(monkeypatch):
    target = {"provider": "groq", "model": "good-model", "base_url": "https://example.invalid", "api_key": "fake"}
    monkeypatch.setattr(coach_module, "configured_targets", lambda: [target])
    exaggerated = {**VALID_COACHING, "ai_rating_10": 10.0, "rating_confidence": "high"}
    async def fake_call_json(client, target, **kwargs):
        return exaggerated
    monkeypatch.setattr(coach_module, "call_json", fake_call_json)
    data = request().json()
    assert data["status"] == "ready"
    # Benchmark anchor is 6.25/10; model cannot rate more than +1.5 points above it.
    assert data["coaching"]["ai_rating_10"] == 7.8
    assert data["coaching"]["rating_adjustment_limited"] is True


def test_ai_rating_rejects_invalid_numeric_value_and_reports_provider_unavailable(monkeypatch):
    target = {"provider": "groq", "model": "good-model", "base_url": "https://example.invalid", "api_key": "fake"}
    monkeypatch.setattr(coach_module, "configured_targets", lambda: [target])
    invalid = {**VALID_COACHING, "ai_rating_10": 99}
    async def fake_call_json(client, target, **kwargs):
        return invalid
    monkeypatch.setattr(coach_module, "call_json", fake_call_json)
    data = request().json()
    assert data["status"] == "unavailable"
    assert data["ai_assist"]["reason"] == "all_providers_failed"
