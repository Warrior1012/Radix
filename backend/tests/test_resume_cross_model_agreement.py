"""Tests for the opt-in cross-provider resume skill comparison."""
import asyncio
import json

from fastapi.testclient import TestClient

from app import app
from radix_jd import resume
from radix_jd.gemini import LLMError
from radix_jd.resume import build_resume_profile
from tests.test_role2_resume import TEXT, good_model_output, resume_docx

client = TestClient(app)


def _targets():
    return [
        {"provider": "gemini", "model": "gemini-primary", "base_url": "https://example.test", "api_key": "test-key"},
        {"provider": "groq", "model": "groq-verifier", "base_url": "https://example.test/v1", "api_key": "test-key"},
    ]


def test_cross_provider_comparison_reports_overlap_and_both_sides_of_disagreement(monkeypatch):
    monkeypatch.setattr(resume, "configured_targets", _targets)
    primary = build_resume_profile(good_model_output(), "llm", "resume.docx", len(TEXT), text=TEXT)["skills"]
    verifier_output = good_model_output(skills=[
        {"skill_name": "Python", "category_code": "COD", "evidence": "built a REST API in Python with PostgreSQL", "confidence": "high"},
        {"skill_name": "Docker", "category_code": "CLOUD", "evidence": "PostgreSQL and Docker deployment", "confidence": "medium"},
        {"skill_name": "Java", "category_code": "COD", "evidence": "implemented minimax search using algorithms and data structures in Java", "confidence": "high"},
    ])
    calls = []

    async def fake_call_json(client_arg, target, **kwargs):
        calls.append(target["provider"])
        return verifier_output

    monkeypatch.setattr(resume, "call_json", fake_call_json)
    response = client.post(
        "/api/parse-resume/compare",
        files={"file": ("resume.docx", resume_docx())},
        data={"primary_model": "gemini:gemini-primary", "primary_skills": json.dumps(primary)},
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert calls == ["groq"]
    assert result["comparison_mode"] == "cross_provider_skill_overlap"
    assert result["summary"]["agreed"] == 2
    assert result["summary"]["primary_only"] == 2
    assert result["summary"]["verifier_only"] == 1
    assert result["summary"]["unique_union"] == 5
    assert result["summary"]["skill_overlap_pct"] == 40
    assert {item["skill_name"] for item in result["agreed"]} == {"Python", "Docker"}
    assert {item["skill_name"] for item in result["primary_only"]} == {"PostgreSQL", "Data Structures and Algorithms"}
    assert {item["skill_name"] for item in result["verifier_only"]} == {"Java"}
    assert "not ground-truth accuracy" in result["disclaimer"]
    assert "email" not in result and "profile" not in result


def test_cross_provider_comparison_requires_a_distinct_provider(monkeypatch):
    monkeypatch.setattr(resume, "configured_targets", lambda: [_targets()[0]])
    response = client.post(
        "/api/parse-resume/compare",
        files={"file": ("resume.docx", resume_docx())},
        data={"primary_model": "gemini:gemini-primary", "primary_skills": "[]"},
    )
    assert response.status_code == 409
    assert "No second AI provider is configured" in response.json()["detail"]


def test_comparison_rejects_invalid_primary_skill_payload(monkeypatch):
    response = client.post(
        "/api/parse-resume/compare",
        files={"file": ("resume.docx", resume_docx())},
        data={"primary_model": "gemini:gemini-primary", "primary_skills": "not-json"},
    )
    assert response.status_code == 422
    assert "valid JSON" in response.json()["detail"]
