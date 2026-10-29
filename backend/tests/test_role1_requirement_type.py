"""Role 1 regression tests for D1 (preferred -> required) and D2 (dishonest analysis_meta)."""
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app import app
from radix_jd.requirement_type import resolve_requirement_type
from tests.gemini_mock import GeminiMock, PREFERRED_LINES, REQUIRED_LINES

client = TestClient(app)
JD_TEXT = (Path(__file__).parent / "fixtures" / "synthetic_jd_sections.txt").read_text(encoding="utf-8")


def jd_docx() -> bytes:
    d = Document()
    for line in JD_TEXT.splitlines():
        if line.strip():
            d.add_paragraph(line)
    b = BytesIO(); d.save(b)
    return b.getvalue()


def analyze(monkeypatch, mock, models="gemini-test-1", fallback=None):
    mock.install(monkeypatch, models)
    if fallback is not None:
        monkeypatch.setenv("DEMO_FALLBACK", fallback)
    return client.post("/api/analyze-jd", files={"file": ("jd.docx", jd_docx())})


REQ_NAMES = [n for n, _, _ in REQUIRED_LINES]
PREF_NAMES = [n for n, _, _ in PREFERRED_LINES]


# ---------- pure resolver ----------
def test_heading_decides_when_model_is_wrong():
    assert resolve_requirement_type("required", "Docker containers", JD_TEXT) == ("preferred", "section_heading")
    assert resolve_requirement_type("preferred", "Python for backend services", JD_TEXT) == ("required", "section_heading")


def test_inline_marker_beats_section_heading():
    text = "Required Skills\n• Python\n• Docker (preferred)\n• Kubernetes is a plus\n"
    assert resolve_requirement_type("required", "Docker (preferred)", text) == ("preferred", "inline_marker")
    assert resolve_requirement_type("required", "Kubernetes is a plus", text) == ("preferred", "inline_marker")
    assert resolve_requirement_type("preferred", "Python", text) == ("required", "section_heading")


def test_same_line_heading_with_items():
    text = "Required Skills: Python, SQL\nPreferred Skills: Docker, Redis\n"
    assert resolve_requirement_type(None, "Python, SQL", text)[0] == "required"
    assert resolve_requirement_type(None, "Docker, Redis", text)[0] == "preferred"


def test_preferred_qualifications_is_not_mistaken_for_required():
    text = "Preferred Qualifications\n• Rust\n"
    assert resolve_requirement_type("required", "Rust", text) == ("preferred", "section_heading")


def test_skill_in_both_sections_is_required():
    text = "Required Skills\n• SQL databases\nPreferred Skills\n• Docker\n• SQL databases\n"
    assert resolve_requirement_type("preferred", "SQL databases", text)[0] == "required"


def test_section_break_stops_inheriting_a_heading():
    text = "Preferred Skills\n• Docker\nResponsibilities:\n• Build Python services\n"
    assert resolve_requirement_type("required", "Build Python services", text) == ("required", "model")


def test_ambiguous_defaults_to_required_and_is_labelled():
    assert resolve_requirement_type(None, "Python", "We use Python daily.") == ("required", "default")
    assert resolve_requirement_type("garbage", "not in text at all", "We use Python daily.") == ("required", "default")


# ---------- end-to-end through the real extractor with mocked Gemini ----------
@pytest.mark.parametrize("mode", ["correct", "all_required", "omitted"])
def test_preferred_stay_preferred_and_required_stay_required(monkeypatch, mode):
    """'all_required' reproduces the live defect (15 required / 0 preferred); 'omitted' = model gave no type."""
    r = analyze(monkeypatch, GeminiMock(mode))
    assert r.status_code == 200, r.text
    d = r.json()
    assert sorted(d["required_skills"]) == sorted(REQ_NAMES)
    assert sorted(d["preferred_skills"]) == sorted(PREF_NAMES)
    assert all(s["requirement_type"] in ("required", "preferred") and s["requirement_basis"] for s in d["skills"])
    assert not set(d["required_skills"]) & set(d["preferred_skills"])
    assert d["analysis_meta"]["requirement_type_corrections"] == (5 if mode == "all_required" else 0)


def test_skill_objects_keep_the_four_contract_fields(monkeypatch):
    d = analyze(monkeypatch, GeminiMock("correct")).json()
    assert d["jd_id"] and d["source_file"] == "jd.docx"
    for s in d["skills"]:
        assert {"skill_name", "category_code", "evidence", "confidence"} <= set(s)
        assert s["evidence"] in JD_TEXT.replace("•", "").replace("\n", " ") or s["evidence"] in JD_TEXT


def test_gemini_request_asks_for_requirement_type(monkeypatch):
    mock = GeminiMock("correct")
    analyze(monkeypatch, mock)
    body = mock.requests[0]["body"]
    props = body["generationConfig"]["responseSchema"]["properties"]["skills"]["items"]["properties"]
    assert props["requirement_type"]["enum"] == ["required", "preferred"]
    assert "requirement_type" in body["generationConfig"]["responseSchema"]["properties"]["skills"]["items"]["required"]
    assert "Preferred" in body["systemInstruction"]["parts"][0]["text"]


# ---------- analysis_meta honesty (D2) ----------
def test_single_model_is_not_reported_as_consensus(monkeypatch):
    d = analyze(monkeypatch, GeminiMock("correct")).json()
    m = d["analysis_meta"]
    assert d["extraction_method"] == "llm"
    assert m["strategy"] == "single_model" and m["processing_path"] == "llm_single"
    assert m["models_invoked"] == ["gemini:gemini-test-1"] and m["models_succeeded"] == 1
    assert "consensus" not in m["note"].lower() or "no consensus" in m["note"].lower()


def test_two_models_both_succeed_is_consensus(monkeypatch):
    d = analyze(monkeypatch, GeminiMock("correct"), models="gemini-a,gemini-b").json()
    m = d["analysis_meta"]
    assert m["strategy"] == "multi_model_consensus" and d["extraction_method"] == "llm_ensemble"
    assert m["models_invoked"] == ["gemini:gemini-a", "gemini:gemini-b"] and m["models_succeeded"] == 2


def test_one_of_two_models_failing_is_reported_as_single_model(monkeypatch):
    d = analyze(monkeypatch, GeminiMock("correct", fail_models=["gemini-b"]), models="gemini-a,gemini-b").json()
    m = d["analysis_meta"]
    assert m["strategy"] == "single_model" and m["models_succeeded"] == 1 and len(m["models_invoked"]) == 2
    assert [f["model"] for f in m["failed_models"]] == ["gemini:gemini-b"]


# ---------- errors and fallback honesty ----------
def test_no_provider_and_fallback_disabled_is_a_clear_error(monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("DEMO_FALLBACK", raising=False)  # default must be OFF
    r = client.post("/api/analyze-jd", files={"file": ("jd.docx", jd_docx())})
    assert r.status_code == 502 and "No AI provider configured" in r.json()["detail"]


def test_explicit_fallback_is_labelled_as_keyword_not_llm(monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DEMO_FALLBACK", "true")
    d = client.post("/api/analyze-jd", files={"file": ("jd.docx", jd_docx())}).json()
    assert d["extraction_method"] == "demo_keyword_fallback"
    assert d["analysis_meta"]["processing_path"] == "keyword_fallback" and d["analysis_meta"]["models_succeeded"] == 0


def test_all_models_failing_with_fallback_off_does_not_fake_success(monkeypatch):
    r = analyze(monkeypatch, GeminiMock(status=429), fallback="false")
    assert r.status_code == 502 and "All configured AI models failed" in r.json()["detail"]
    assert "fake-test-key" not in r.text


def test_malformed_json_from_model_is_an_error_not_empty_success(monkeypatch):
    r = analyze(monkeypatch, GeminiMock(raw_text="this is not json"), fallback="false")
    assert r.status_code == 502


def test_ungrounded_evidence_is_rejected(monkeypatch):
    import json as _j
    bad = _j.dumps({"company": "X", "role": "Y", "skills": [{"skill_name": "Quantum Basket Weaving", "category_code": "OTHER",
                    "evidence": "quantum basket weaving certification mandatory", "confidence": "high", "requirement_type": "required"}]})
    r = analyze(monkeypatch, GeminiMock(raw_text=bad), fallback="false")
    assert r.status_code == 502  # nothing grounded in the JD -> no invented skills
