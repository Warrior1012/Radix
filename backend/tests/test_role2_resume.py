"""Role 2 (Resume Parsing) tests for D3a-e. Fixture is SYNTHETIC (official resumes were not supplied)."""
import json
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app import app
from radix_jd.gemini import LLMError
from radix_jd.resume import build_resume_profile
from tests.gemini_mock import GeminiMock

client = TestClient(app)
TEXT = (Path(__file__).parent / "fixtures" / "synthetic_resume.txt").read_text(encoding="utf-8")
CONTRACT_KEYS = {"skill_name", "category_code", "evidence", "confidence"}


def resume_docx() -> bytes:
    d = Document()
    for line in TEXT.splitlines():
        if line.strip():
            d.add_paragraph(line)
    b = BytesIO(); d.save(b)
    return b.getvalue()


def resume_pdf() -> bytes:
    pytest.importorskip("reportlab")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    b = BytesIO(); c = canvas.Canvas(b, pagesize=A4); y = 800
    for line in TEXT.splitlines():
        c.drawString(40, y, line); y -= 14
    c.save()
    return b.getvalue()


def good_model_output(**over):
    out = {
        "name": "Test Candidate One", "email": "test.candidate@example.com",
        "education": ["B.Tech in Computer Science, Example Institute of Technology, 2022-2026"],
        "skills": [
            {"skill_name": "Python", "category_code": "COD", "evidence": "built a REST API in Python with PostgreSQL", "confidence": "high"},
            {"skill_name": "PostgreSQL", "category_code": "SQL", "evidence": "REST API in Python with PostgreSQL and Docker", "confidence": "high"},
            {"skill_name": "Docker", "category_code": "CLOUD", "evidence": "PostgreSQL and Docker deployment", "confidence": "medium"},
            {"skill_name": "Data Structures and Algorithms", "category_code": "DSA", "evidence": "algorithms and data structures in Java", "confidence": "high"},
        ],
        "projects": ["Expense Tracker API - built a REST API in Python with PostgreSQL and Docker deployment."],
        "experience": [], "internships": ["Backend Intern, Example Labs, Jun 2025 - Aug 2025: wrote SQL queries and Python scripts."],
        "hackathons": ["Smart India Hackathon 2024 - finalist, built a route optimiser."],
        "certifications": ["AWS Cloud Practitioner"], "preferred_roles": ["Backend Engineer"],
    }
    out.update(over)
    return out


def parse(monkeypatch, mock, fname="resume.docx", content=None, fallback=None):
    mock.install(monkeypatch)
    if fallback is not None:
        monkeypatch.setenv("DEMO_FALLBACK", fallback)
    return client.post("/api/parse-resume", files={"file": (fname, content or resume_docx())})


# ---------- happy path, both formats ----------
@pytest.mark.parametrize("kind", ["docx", "pdf"])
def test_rich_extraction_both_formats(monkeypatch, kind):
    content = resume_docx() if kind == "docx" else resume_pdf()
    r = parse(monkeypatch, GeminiMock(raw_text=json.dumps(good_model_output())), f"resume.{kind}", content)
    assert r.status_code == 200, r.text
    p = r.json()["profile"]
    assert p["name"] == "Test Candidate One" and p["email"] == "test.candidate@example.com"
    assert p["hackathons"] and p["internships"] and p["certifications"] == ["AWS Cloud Practitioner"]
    assert p["preferred_roles"] == ["Backend Engineer"]
    assert p["education_entries"] and p["education"].startswith("B.Tech")
    assert {s["skill_name"] for s in p["skills"]} == {"Python", "PostgreSQL", "Docker", "Data Structures and Algorithms"}
    assert all(CONTRACT_KEYS <= set(s) for s in p["skills"])
    assert p["parsing_method"] == "llm"


# ---------- D3b: no fabricated evidence ----------
def test_skill_without_supported_evidence_is_dropped_not_given_placeholder(monkeypatch):
    out = good_model_output()
    out["skills"].append({"skill_name": "Kubernetes", "category_code": "CLOUD", "evidence": "ran large k8s clusters in production", "confidence": "high"})
    out["skills"].append({"skill_name": "Rust", "category_code": "COD", "evidence": "", "confidence": "high"})
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(out))).json()["profile"]
    names = {s["skill_name"] for s in p["skills"]}
    assert "Kubernetes" not in names and "Rust" not in names
    assert set(p["extraction_notes"]["dropped_skills_unsupported"]) == {"Kubernetes", "Rust"}
    assert all(s["evidence"] != "Mentioned in uploaded resume" for s in p["skills"])


def test_paraphrased_evidence_is_repaired_from_real_text_and_labelled(monkeypatch):
    out = good_model_output(skills=[{"skill_name": "Git", "category_code": "SWE", "evidence": "uses version control daily", "confidence": "high"}])
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(out))).json()["profile"]
    s = p["skills"][0]
    assert s["evidence_basis"] == "repaired_from_text"
    assert "Git" in s["evidence"] and s["evidence"] in " ".join(TEXT.split()) or "Git" in s["evidence"]


def test_verbatim_evidence_is_labelled_quote(monkeypatch):
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(good_model_output()))).json()["profile"]
    assert {s["evidence_basis"] for s in p["skills"]} == {"quote"}


def test_fabricated_list_items_and_identity_are_dropped(monkeypatch):
    out = good_model_output(
        name="Somebody Else", email="fake@nowhere.org",
        hackathons=["Google Code Jam 2023 winner"], certifications=["AWS Cloud Practitioner", "Certified Kubernetes Administrator"],
        internships=["Quant Intern at Jane Street"], preferred_roles=["Chief Technology Officer"])
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(out))).json()["profile"]
    assert p["name"] == ""                                   # not in resume text -> not trusted
    assert p["email"] == "test.candidate@example.com"        # repaired from text, labelled
    assert p["extraction_notes"]["email_source"] == "regex_from_text"
    assert p["hackathons"] == [] and p["internships"] == [] and p["preferred_roles"] == []
    assert p["certifications"] == ["AWS Cloud Practitioner"]
    assert p["extraction_notes"]["dropped_items_unsupported"]["hackathons"] == 1


# ---------- D3c: nothing hard-coded ----------
def test_lists_are_empty_when_resume_has_none(monkeypatch):
    out = good_model_output(hackathons=[], internships=[], preferred_roles=[], certifications=[], projects=[])
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(out))).json()["profile"]
    assert p["hackathons"] == p["internships"] == p["preferred_roles"] == []


def test_lists_are_populated_when_resume_has_them_not_hardcoded_empty(monkeypatch):
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(good_model_output()))).json()["profile"]
    assert p["hackathons"] != [] and p["internships"] != [] and p["preferred_roles"] != []


def test_prompt_and_schema_request_the_rich_fields(monkeypatch):
    mock = GeminiMock(raw_text=json.dumps(good_model_output()))
    parse(monkeypatch, mock)
    body = mock.requests[0]["body"]
    prompt = body["systemInstruction"]["parts"][0]["text"]
    props = body["generationConfig"]["responseSchema"]["properties"]
    for f in ("hackathons", "internships", "preferred_roles", "projects", "certifications", "experience", "education"):
        assert f in props and f in prompt
    assert "VERBATIM" in prompt and "Do NOT infer proficiency" in prompt
    assert "<RESUME>" in body["contents"][0]["parts"][0]["text"]
    assert "fake-test-key" not in json.dumps(body)            # key only in query params, never in the body


# ---------- D3d: level is never produced ----------
def test_no_level_is_ever_emitted_even_if_model_returns_one(monkeypatch):
    out = good_model_output()
    for s in out["skills"]:
        s["level"] = 9; s["proficiency"] = "expert"
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(out))).json()["profile"]
    assert all("level" not in s and "proficiency" not in s for s in p["skills"])


# ---------- D3e: category repair is labelled ----------
def test_invalid_category_is_repaired_and_labelled_valid_one_is_untouched(monkeypatch):
    out = good_model_output(skills=[
        {"skill_name": "PostgreSQL", "category_code": "DATABASES", "evidence": "REST API in Python with PostgreSQL", "confidence": "high"},
        {"skill_name": "Docker", "category_code": "OTHER", "evidence": "PostgreSQL and Docker deployment", "confidence": "high"}])
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(out))).json()["profile"]
    by = {s["skill_name"]: s for s in p["skills"]}
    assert by["PostgreSQL"]["category_code"] == "SQL" and by["PostgreSQL"]["category_repaired"] is True
    assert by["Docker"]["category_code"] == "OTHER" and "category_repaired" not in by["Docker"]  # model's valid choice is respected
    assert p["extraction_notes"]["category_repairs"] == 1


def test_duplicate_skills_are_merged():
    data = good_model_output(skills=[
        {"skill_name": "Python", "category_code": "COD", "evidence": "Python", "confidence": "high"},
        {"skill_name": "python", "category_code": "COD", "evidence": "Python scripts", "confidence": "low"}])
    p = build_resume_profile(data, "llm", "r.docx", len(TEXT), text=TEXT)
    assert [s["skill_name"] for s in p["skills"]] == ["Python"]


# ---------- D3a: real error causes ----------
@pytest.mark.parametrize("status,kind", [(401, "auth"), (403, "auth"), (404, "model_not_found"), (429, "rate_limited")])
def test_real_provider_failure_cause_is_surfaced(monkeypatch, status, kind):
    r = parse(monkeypatch, GeminiMock(status=status), fallback="false")
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert kind in detail and f"HTTP {status}" in detail
    assert "No keyword fallback was used" in detail
    assert "fake-test-key" not in r.text


def test_bad_json_from_model_is_reported_as_bad_json(monkeypatch):
    r = parse(monkeypatch, GeminiMock(raw_text="Sure! Here is the resume: {not json"), fallback="false")
    assert r.status_code == 502 and "bad_json" in r.json()["detail"]


def test_non_object_json_is_reported(monkeypatch):
    r = parse(monkeypatch, GeminiMock(raw_text="[1,2,3]"), fallback="false")
    assert r.status_code == 502 and "bad_structure" in r.json()["detail"]


def test_no_provider_configured_says_so(monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DEMO_FALLBACK", "false")
    r = client.post("/api/parse-resume", files={"file": ("resume.docx", resume_docx())})
    assert r.status_code == 502 and "no AI provider configured" in r.json()["detail"]


def test_parse_resume_llm_raises_typed_error_not_none(monkeypatch):
    import asyncio
    from radix_jd.resume import parse_resume_llm
    GeminiMock(status=429).install(monkeypatch)
    with pytest.raises(LLMError) as ei:
        asyncio.run(parse_resume_llm(TEXT))
    assert ei.value.kind == "rate_limited"


# ---------- fallback honesty ----------
def test_fallback_only_when_enabled_and_is_labelled_with_the_real_reason(monkeypatch):
    r = parse(monkeypatch, GeminiMock(status=401), fallback="true")
    assert r.status_code == 200
    j = r.json(); p = j["profile"]
    assert j["extraction_method"] == "demo_keyword_fallback" and p["parsing_method"] == "demo_keyword_fallback"
    assert "auth" in p["notice"] and "not AI" in p["notice"]
    assert p["hackathons"] == [] and all("level" not in s for s in p["skills"])
    assert p["skills"], "keyword fallback still finds real keywords"
    assert all(s["evidence"] and s["evidence"] != "Mentioned in uploaded resume" for s in p["skills"])


# ---------- hand-off shape is valid for Profile (Role 3) ----------
def test_handoff_validates_as_profile_and_saves(monkeypatch):
    p = parse(monkeypatch, GeminiMock(raw_text=json.dumps(good_model_output()))).json()["profile"]
    saved = client.post("/api/profile", json=p)
    assert saved.status_code == 200, saved.text
    loaded = saved.json()["profile"]
    assert loaded["hackathons"] == p["hackathons"] and loaded["internships"] == p["internships"]
    assert loaded["preferred_roles"] == ["Backend Engineer"]
    assert len(loaded["skills"]) == 4


def test_resume_parser_falls_back_to_next_provider_after_primary_fails(monkeypatch):
    import asyncio
    from radix_jd import resume

    targets = [
        {"provider": "gemini", "model": "gemini-test", "base_url": "https://example.test", "api_key": "not-a-real-key"},
        {"provider": "groq", "model": "groq-test", "base_url": "https://example.test/v1", "api_key": "not-a-real-key"},
        {"provider": "openrouter", "model": "router-test", "base_url": "https://example.test/v1", "api_key": "not-a-real-key"},
    ]
    monkeypatch.setattr(resume, "configured_targets", lambda: targets)
    monkeypatch.setenv("RESUME_PROVIDER_ORDER", "gemini,groq,openrouter")
    calls = []

    async def fake_call_json(client, target, **kwargs):
        calls.append(target["provider"])
        if target["provider"] == "gemini":
            raise LLMError("rate_limited", "simulated rate limit", model=target["model"], provider=target["provider"])
        return good_model_output()

    monkeypatch.setattr(resume, "call_json", fake_call_json)
    result = asyncio.run(resume.parse_resume_llm(TEXT))
    assert calls == ["gemini", "groq"]
    assert result["_model"] == "groq:groq-test"
    assert result["_ai_attempts"]["fallback_used"] is True
    assert result["_ai_attempts"]["failed"][0]["kind"] == "rate_limited"


def test_resume_parser_tries_remaining_providers_if_all_fail(monkeypatch):
    import asyncio
    from radix_jd import resume

    targets = [
        {"provider": "gemini", "model": "gemini-test", "base_url": "https://example.test", "api_key": "not-a-real-key"},
        {"provider": "groq", "model": "groq-test", "base_url": "https://example.test/v1", "api_key": "not-a-real-key"},
    ]
    monkeypatch.setattr(resume, "configured_targets", lambda: targets)
    monkeypatch.setenv("RESUME_PROVIDER_ORDER", "gemini,groq")
    calls = []

    async def fake_call_json(client, target, **kwargs):
        calls.append(target["provider"])
        raise LLMError("rate_limited", "simulated rate limit", model=target["model"], provider=target["provider"])

    monkeypatch.setattr(resume, "call_json", fake_call_json)
    with pytest.raises(LLMError) as exc:
        asyncio.run(resume.parse_resume_llm(TEXT))
    assert calls == ["gemini", "groq"]
    assert exc.value.kind == "all_providers_failed"
    assert "gemini:gemini-test" in str(exc.value) and "groq:groq-test" in str(exc.value)
