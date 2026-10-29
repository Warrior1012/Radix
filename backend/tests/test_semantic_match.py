"""Offline tests for the optional evidence-grounded AI semantic match assist."""
import asyncio
from radix_jd.gemini import LLMError
from radix_jd import semantic_match


def test_semantic_assist_falls_back_between_providers_and_validates_labels(monkeypatch):
    targets = [
        {"provider": "groq", "model": "groq-test", "base_url": "https://example.test/v1", "api_key": "not-a-real-key"},
        {"provider": "gemini", "model": "gemini-test", "base_url": "https://example.test", "api_key": "not-a-real-key"},
        {"provider": "openrouter", "model": "router-test", "base_url": "https://example.test/v1", "api_key": "not-a-real-key"},
    ]
    monkeypatch.setattr(semantic_match, "configured_targets", lambda: targets)
    monkeypatch.setenv("SKILL_MATCH_PROVIDER_ORDER", "groq,gemini,openrouter")
    calls = []

    async def fake_call_json(client, target, **kwargs):
        calls.append(target["provider"])
        if target["provider"] == "groq":
            raise LLMError("rate_limited", "simulated", model=target["model"], provider=target["provider"])
        return {"matches": [{
            "jd_skill": "FastAPI framework service implementation",
            "candidate_skill": "FastAPI",
            "reason": "Resume evidence shows FastAPI REST API development.",
            "confidence": "high",
        }]}

    monkeypatch.setattr(semantic_match, "call_json", fake_call_json)
    candidates = [{"skill_name": "FastAPI", "category_code": "COD", "evidence": "Built REST APIs with FastAPI"}]
    job = {"required_skills": ["FastAPI framework service implementation"], "preferred_skills": [], "skills": [{
        "skill_name": "FastAPI framework service implementation", "category_code": "COD",
        "requirement_type": "required", "evidence": "FastAPI framework service implementation is required",
    }]}
    mapping, meta = asyncio.run(semantic_match.suggest_semantic_matches(candidates, job, job["required_skills"]))
    assert calls == ["groq", "gemini"]
    assert mapping == {semantic_match.canonical("FastAPI framework service implementation"): "FastAPI"}
    assert meta["applied"] is True and meta["provider_used"] == "gemini" and meta["fallback_used"] is True


def test_semantic_assist_needs_grounded_evidence_and_skips_when_no_provider(monkeypatch):
    monkeypatch.setattr(semantic_match, "configured_targets", lambda: [])
    mapping, meta = asyncio.run(semantic_match.suggest_semantic_matches(
        [{"skill_name": "FastAPI", "category_code": "COD", "evidence": "Built a FastAPI API"}],
        {"required_skills": ["FastAPI framework service implementation"], "skills": []},
        ["FastAPI framework service implementation"],
    ))
    assert mapping == {} and meta["reason"] == "no_ai_provider_configured"
