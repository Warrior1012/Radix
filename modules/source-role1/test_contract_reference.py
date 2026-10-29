import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.schemas import Skill, CATEGORY_CODES
from app.extractor import demo_extract

def test_category_codes_match_shared_contract():
    assert {"DSA", "COD", "OOD", "APTI", "COMM", "AI", "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS", "OTHER"} == CATEGORY_CODES

def test_skill_validation_normalizes_code():
    skill = Skill(skill_name="Python", category_code="cod", evidence="Python required", confidence="high")
    assert skill.category_code == "COD"

def test_skill_validation_normalizes_confidence():
    skill = Skill(skill_name="Python", category_code="COD", evidence="Python required", confidence="HIGH")
    assert skill.confidence == "high"

def test_unknown_category_is_rejected():
    try:
        Skill(skill_name="Python", category_code="PY", evidence="Python required", confidence="high")
    except Exception:
        return
    assert False, "Unknown category should be rejected"

def test_demo_extractor_returns_contract_items():
    result = demo_extract("We need Python, SQL, data structures and system design.")
    assert result["skills"]
    assert all({"skill_name", "category_code", "evidence", "confidence"} <= set(s) for s in result["skills"])

def test_evidence_grounding_rejects_unrelated_claims():
    from app.extractor import _evidence_supported
    source = "The candidate must know Python and SQL and have experience with REST APIs."
    assert _evidence_supported("must know Python and SQL", source)
    assert not _evidence_supported("Expert in quantum welding and aerospace composites", source)

def test_consensus_merges_same_skill_and_tracks_votes():
    from app.extractor import _merge_outputs
    source = "Python and SQL are required for this role."
    outputs = [
        {"model": "model-a", "company": "Acme", "role": "Engineer", "skills": [
            {"skill_name": "Python", "category_code": "COD", "evidence": "Python is required", "confidence": "high"}]},
        {"model": "model-b", "company": "Acme", "role": "Engineer", "skills": [
            {"skill_name": "Python", "category_code": "COD", "evidence": "Python is required", "confidence": "medium"},
            {"skill_name": "SQL", "category_code": "SQL", "evidence": "SQL are required", "confidence": "high"}]},
    ]
    skills, meta = _merge_outputs(outputs, source)
    assert len([s for s in skills if s["skill_name"] == "Python"]) == 1
    assert next(v for v in meta["skill_votes"] if v["skill_name"] == "Python")["model_votes"] == 2
    assert {"skill_name", "category_code", "evidence", "confidence"} == set(skills[0])

def test_parallel_ensemble_survives_one_model_failure(monkeypatch):
    import asyncio
    import app.extractor as extractor
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODELS", "model-a,model-b,model-c")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("DEMO_FALLBACK", "false")

    async def fake_call(client, target, text):
        model = target["model"]
        if model == "model-b":
            raise RuntimeError("simulated rate limit")
        return {"model": f"{target['provider']}:{model}", "provider": target["provider"], "company": "Acme", "role": "Engineer", "skills": [
            {"skill_name": "Python", "category_code": "COD", "evidence": "Python is required", "confidence": "high"}]}

    monkeypatch.setattr(extractor, "_call_model", fake_call)
    result = asyncio.run(extractor.extract_with_llm("Acme is hiring an Engineer. Python is required for this role."))
    assert result["extraction_method"] == "llm_ensemble"
    assert result["analysis_meta"]["models_succeeded"] == 2
    assert result["analysis_meta"]["failed_models"][0]["model"] == "groq:model-b"
    assert result["skills"][0]["skill_name"] == "Python"


def test_all_models_fail_can_be_strict(monkeypatch):
    import asyncio
    import app.extractor as extractor
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_MODELS", "model-a")
    monkeypatch.setenv("DEMO_FALLBACK", "false")

    async def fake_call(client, target, text):
        raise RuntimeError("simulated unavailable model")

    monkeypatch.setattr(extractor, "_call_model", fake_call)
    try:
        asyncio.run(extractor.extract_with_llm("A sufficiently long job description with Python requirements."))
    except RuntimeError as exc:
        assert "All configured AI models failed" in str(exc)
    else:
        assert False, "Strict mode must not silently fall back to demo output"


def test_provider_configuration_is_independent_and_secret_free_in_metadata(monkeypatch):
    import app.extractor as extractor
    monkeypatch.setenv("GROQ_API_KEY", "g-key")
    monkeypatch.setenv("GROQ_MODELS", "openai/gpt-oss-20b")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_MODELS", "google/gemma-4-31b-it:free")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    monkeypatch.setenv("GEMINI_MODELS", "gemini-3.8-flash")
    targets = extractor.configured_targets()
    assert {(t["provider"], t["model"]) for t in targets} == {
        ("groq", "openai/gpt-oss-20b"),
        ("openrouter", "google/gemma-4-31b-it:free"),
        ("gemini", "gemini-3.8-flash"),
    }
    assert all("api_key" in t for t in targets)  # used internally; health output exposes labels only
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("OPENROUTER_API_KEY")
    monkeypatch.delenv("GEMINI_API_KEY")
    assert extractor.configured_targets() == []


def test_gemini_adapter_parses_schema_json_response():
    import asyncio
    import httpx
    from app.extractor import _call_model

    def handler(request):
        assert request.url.path.endswith("/models/gemini-test:generateContent")
        assert request.url.params.get("key") == "secret-test-key"
        payload = json.loads(request.content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        body = {"candidates": [{"content": {"parts": [{"text": json.dumps({
            "company": "Acme", "role": "Engineer", "skills": [{
                "skill_name": "Python", "category_code": "COD", "evidence": "Python is required", "confidence": "high"
            }]
        })}]}}]}
        return httpx.Response(200, json=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _call_model(client, {"provider": "gemini", "model": "gemini-test",
                "base_url": "https://gemini.test/v1beta", "api_key": "secret-test-key"},
                "Acme requires Python for this Engineer role.")

    result = asyncio.run(run())
    assert result["model"] == "gemini:gemini-test"
    assert result["skills"][0]["skill_name"] == "Python"

def test_model_adapter_truncates_grounded_evidence_before_contract_validation():
    import asyncio
    import httpx
    from app.extractor import _call_model

    source = "Python is required. " + ("Additional role details. " * 30)
    long_evidence = source

    def handler(request):
        body = {"choices": [{"message": {"content": json.dumps({
            "company": "Acme", "role": "Engineer", "skills": [{
                "skill_name": "Python", "category_code": "COD",
                "evidence": long_evidence, "confidence": "HIGH"
            }]
        })}}]}
        return httpx.Response(200, json=body)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _call_model(client, {"provider": "groq", "model": "groq-test",
                "base_url": "https://groq.test/openai/v1", "api_key": "test-key"}, source)

    result = asyncio.run(run())
    assert result["skills"][0]["confidence"] == "high"
    assert len(result["skills"][0]["evidence"]) <= 500


def test_openrouter_adapter_uses_openai_compatible_json_mode():
    import asyncio
    import httpx
    from app.extractor import _call_model

    def handler(request):
        assert request.url.path == "/api/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer router-test-key"
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "company": "Acme", "role": "Engineer", "skills": [{
                "skill_name": "Python", "category_code": "COD", "evidence": "Python is required", "confidence": "high"
            }]
        })}}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await _call_model(client, {"provider": "openrouter", "model": "router-test",
                "base_url": "https://router.test/api/v1", "api_key": "router-test-key"},
                "Acme requires Python for this Engineer role.")

    result = asyncio.run(run())
    assert result["model"] == "openrouter:router-test"
    assert result["provider"] == "openrouter"
