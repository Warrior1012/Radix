"""Phase 8: whole-system checks. Fixtures are SYNTHETIC (official JDs/resumes were not supplied).
Gemini is a mock transport (real extractor/prompt/grounding code runs); no network, no keys."""
import json, os, re, socket, subprocess, sys, time
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from docx import Document
from fastapi.testclient import TestClient

from app import app
from tests.gemini_mock import GeminiMock
from tests.test_role2_resume import good_model_output

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
FIX = Path(__file__).parent / "fixtures"
client = TestClient(app)
KEY_VARS = ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GOOGLE_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
CODES = ["COD", "DSA", "OOD", "APTI", "COMM", "AI", "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS"]


def docx_bytes(fixture: str) -> bytes:
    d = Document()
    for line in (FIX / fixture).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d.add_paragraph(line)
    b = BytesIO(); d.save(b)
    return b.getvalue()


@pytest.fixture
def no_keys(monkeypatch):
    for k in KEY_VARS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("DEMO_FALLBACK", raising=False)


# ---------------------------------------------------------------- end-to-end flow
def test_full_flow_and_candidates_get_visibly_different_results(monkeypatch):
    """Brief DoD 2+3: wired flow works, and Talent Check / Skill Match differ per candidate."""
    mock = GeminiMock(); mock.install(monkeypatch)
    monkeypatch.delenv("DEMO_FALLBACK", raising=False)

    # 1-2. health + company list
    assert client.get("/api/health").json()["status"] == "ok"
    companies = client.get("/api/companies").json()
    snap = [c for c in companies if c["source"] == "snapshot"]
    assert len(snap) == 3

    # 3. JD analytics (mock returns JD skills)
    r = client.post("/api/analyze-jd", files={"file": ("jd.docx", docx_bytes("synthetic_jd_sections.txt"))})
    assert r.status_code == 200, r.text
    jd = r.json()
    assert jd["jd_id"] and jd["required_skills"] and jd["preferred_skills"]
    assert set(jd["required_skills"]).isdisjoint(jd["preferred_skills"])

    # 4. resume parsing (same mock transport, new payload)
    mock.raw_text = json.dumps(good_model_output())
    r = client.post("/api/parse-resume", files={"file": ("resume.docx", docx_bytes("synthetic_resume.txt"))})
    assert r.status_code == 200, r.text
    parsed = r.json()["profile"]
    assert all("level" not in s or s["level"] is None for s in parsed["skills"]), "parser must never assign a level"

    # 5. merge into a blank profile, 6. user assigns levels, 7. save, 8. load
    r = client.post("/api/profile/merge-resume", json={"profile": {"name": "", "skills": []}, "parsed": parsed})
    assert r.status_code == 200, r.text
    strong = r.json()["profile"]
    for s in strong["skills"]:
        s["level"] = 9
    r = client.post("/api/profile", json=strong)
    assert r.status_code == 200, r.text
    cid = r.json()["profile"]["candidate_id"]
    loaded = client.get(f"/api/profile/{cid}").json()
    assert loaded["name"] == strong["name"] and all(s["level"] == 9 for s in loaded["skills"])

    weak = {"name": "Weak Candidate", "skills": [{"skill_name": "Python", "category_code": "COD", "level": 2}]}
    unassessed = {"name": "Blank Candidate", "skills": [{"skill_name": "Python", "category_code": "COD"}]}

    # 9. Talent Check: every company, every candidate; 12 codes, joins by code
    scores = {}
    for c in snap:
        for label, prof in (("strong", loaded), ("weak", weak), ("blank", unassessed)):
            r = client.post("/api/talent-check", json={"profile": prof, "company_id": c["company_id"]})
            assert r.status_code == 200, r.text
            t = r.json()
            assert sorted(g["category_code"] for g in t["skillset_gap"]) == sorted(CODES)
            scores[(c["short_name"], label)] = t["readiness_score"]
            if label == "blank":
                assert t["readiness_score"] is None, "nothing assessed must not produce a number"
    for c in snap:
        name = c["short_name"]
        assert scores[(name, "strong")] != scores[(name, "weak")], f"{name}: scoring is constant across candidates"

    # 10. Skill Match through the saved-JD handoff (jd_id only, no client lists)
    m_strong = client.post("/api/skill-match", json={"profile": loaded, "jd_id": jd["jd_id"]}).json()
    m_weak = client.post("/api/skill-match", json={"profile": weak, "jd_id": jd["jd_id"]}).json()
    assert m_strong["jd_resolution"] == "jd_id" and m_weak["jd_resolution"] == "jd_id"
    assert m_strong["match_score"] > m_weak["match_score"]
    assert len(m_weak["missing_skills"]) > len(m_strong["missing_skills"])
    assert m_weak["gaps"] and all("why" in g for g in m_weak["gaps"])
    for key in ("jd_source_file", "match_score", "matched_skills", "missing_skills"):
        assert key in m_strong, f"contract key missing: {key}"


# ---------------------------------------------------------------- fallback honesty
@pytest.mark.parametrize("url,fixture", [("/api/analyze-jd", "synthetic_jd_sections.txt"), ("/api/parse-resume", "synthetic_resume.txt")])
def test_no_provider_and_fallback_off_is_an_error_not_silent_keywords(no_keys, url, fixture):
    r = client.post(url, files={"file": ("x.docx", docx_bytes(fixture))})
    assert r.status_code == 502
    assert "No keyword fallback" in r.text or "No AI provider" in r.text


@pytest.mark.parametrize("url,fixture", [("/api/analyze-jd", "synthetic_jd_sections.txt"), ("/api/parse-resume", "synthetic_resume.txt")])
def test_fallback_on_is_explicitly_labelled(no_keys, monkeypatch, url, fixture):
    monkeypatch.setenv("DEMO_FALLBACK", "true")
    r = client.post(url, files={"file": ("x.docx", docx_bytes(fixture))})
    assert r.status_code == 200
    body = r.json()
    assert body["extraction_method"] == "demo_keyword_fallback"
    if "profile" in body:
        assert "not AI" in body["profile"]["notice"]
    else:
        assert body["analysis_meta"]["processing_path"] == "keyword_fallback"


def test_provider_failure_surfaces_real_cause_when_fallback_off(monkeypatch):
    GeminiMock(status=429).install(monkeypatch)
    monkeypatch.delenv("DEMO_FALLBACK", raising=False)
    r = client.post("/api/parse-resume", files={"file": ("x.docx", docx_bytes("synthetic_resume.txt"))})
    assert r.status_code == 502 and "rate_limited" in r.text
    assert "fake-test-key" not in r.text


def test_provider_failure_with_fallback_on_says_why(monkeypatch):
    GeminiMock(status=429).install(monkeypatch)
    monkeypatch.setenv("DEMO_FALLBACK", "true")
    r = client.post("/api/parse-resume", files={"file": ("x.docx", docx_bytes("synthetic_resume.txt"))})
    assert r.status_code == 200
    assert r.json()["profile"]["parsing_method"] == "demo_keyword_fallback"
    assert "rate_limited" in r.json()["profile"]["notice"]


# ---------------------------------------------------------------- secrets
SECRET_PATTERNS = {
    "google api key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "openai-style key": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
    "groq key": re.compile(r"\bgsk_[A-Za-z0-9]{20,}"),
    "openrouter key": re.compile(r"\bsk-or-[A-Za-z0-9_\-]{20,}"),
    "jwt (supabase keys are JWTs)": re.compile(r"\beyJ[A-Za-z0-9_\-]{15,}\.[A-Za-z0-9_\-]{15,}\.[A-Za-z0-9_\-]{10,}"),
    "supabase secret key": re.compile(r"\bsb_secret_[A-Za-z0-9_\-]{10,}"),
}
SKIP_DIRS = {"node_modules", "dist", ".venv", "__pycache__", ".pytest_cache", ".git"}
TEXT_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json", ".sql", ".txt", ".css", ".html", ".bat", ".sh", ".example", ".yml", ".yaml", ".toml", ".cfg", ".env"}


def scan_tree(root: Path):
    hits = []
    for p in root.rglob("*"):
        if not p.is_file() or SKIP_DIRS & set(p.relative_to(root).parts):
            continue
        if p.suffix.lower() not in TEXT_EXT and p.name != ".env.example" and p.name != ".gitignore":
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, rx in SECRET_PATTERNS.items():
            if rx.search(text):
                hits.append((str(p.relative_to(root)), label))
    return hits


def test_no_secrets_in_repo_text_files():
    assert scan_tree(ROOT) == []


def test_secret_scanner_actually_detects_a_planted_key(tmp_path):
    (tmp_path / "leak.py").write_text('KEY = "AIza' + "a" * 35 + '"\n')
    (tmp_path / "ok.py").write_text("KEY = os.getenv('GEMINI_API_KEY')\n")
    assert scan_tree(tmp_path) == [("leak.py", "google api key")]


def test_env_files_are_not_shipped_and_are_git_ignored():
    real = [p for p in ROOT.rglob(".env") if not (SKIP_DIRS & set(p.relative_to(ROOT).parts))]
    # a developer's own local .env is allowed on disk, but must be ignored by git and absent from snapshots
    gi = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in gi and "backend/.env" in gi
    snap = (ROOT / "snapshot.sh").read_text()
    assert "'*/.env'" in snap
    del real


def test_env_example_has_no_secret_values():
    for line in (BACKEND / ".env.example").read_text().splitlines():
        k, _, v = line.partition("=")
        if k.endswith(("_KEY", "_ROLE_KEY")) or k in ("SUPABASE_URL",):
            assert v.strip() == "", f"{k} must be empty in .env.example"


def test_frontend_never_references_server_secrets():
    for p in (ROOT / "frontend" / "src").rglob("*"):
        if p.is_file():
            t = p.read_text(encoding="utf-8", errors="ignore")
            for needle in ("SERVICE_ROLE", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
                assert needle not in t, f"{needle} referenced in frontend {p.name}"


# ---------------------------------------------------------------- startup
def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def test_server_boots_with_no_env_and_answers_health(tmp_path):
    """Real uvicorn process, scrubbed environment: proves startup does not depend on keys or a .env."""
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if k not in KEY_VARS and k != "DEMO_FALLBACK"}
    env.update(PROFILE_STORE_DIR=str(tmp_path / "p"), JD_STORE_DIR=str(tmp_path / "j"), PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", str(port), "--log-level", "warning"],
                            cwd=BACKEND, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        body = None
        for _ in range(60):
            if proc.poll() is not None:
                pytest.fail("server exited early:\n" + proc.stdout.read().decode(errors="ignore")[-800:])
            try:
                body = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1).json(); break
            except httpx.HTTPError:
                time.sleep(0.25)
        assert body and body["status"] == "ok"
        assert body["llm_configured"] is False and body["demo_fallback"] is False
        assert body["storage_mode"] == "local-file"
        assert len(httpx.get(f"http://127.0.0.1:{port}/api/companies").json()) >= 3
    finally:
        proc.terminate()
        try: proc.wait(5)
        except subprocess.TimeoutExpired: proc.kill()
