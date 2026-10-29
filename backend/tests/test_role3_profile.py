"""Role 3 (Profile Builder) tests: D4a validation, D4b merge-not-overwrite, D4c persistence/restart, error paths."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module
from app import app
from radix_jd.profiles import FileProfileStore, merge_resume_into_profile
from tests.gemini_mock import GeminiMock
from tests.test_role2_resume import good_model_output, resume_docx

client = TestClient(app)
BACKEND = Path(__file__).resolve().parent.parent


def sk(name="Python", cat="COD", **kw):
    return {"skill_name": name, "category_code": cat, "evidence": "Built Python apps", "confidence": "high", **kw}


def save(**over):
    body = {"name": "Test Person", "email": "t@example.com", "skills": [sk(level=7)], **over}
    r = client.post("/api/profile", json=body)
    assert r.status_code == 200, r.text
    return r.json()["profile"]


# ------------------------------------------------------------------ D4a validation
@pytest.mark.parametrize("bad", [
    {"skills": [sk(cat="DATABASES")]},
    {"skills": [sk(confidence="certain")]},
    {"skills": [sk(level=11)]}, {"skills": [sk(level=-1)]}, {"skills": [sk(level="expert")]}, {"skills": [sk(level=True)]},
    {"skills": [sk(level=5.5)]},
    {"skills": [{"category_code": "COD"}]},
    {"skills": [{"skill_name": "   ", "category_code": "COD"}]},
    {"email": "not-an-email"}, {"cv_file": "cv.txt"}, {"candidate_id": "../evil"}, {"candidate_id": "a.b"},
    {"hackathons": "Hack A"}, {"hackathons": [1, 2]}, {"skills": "Python"},
])
def test_invalid_profile_is_rejected_with_422(bad):
    r = client.post("/api/profile", json={"name": "X", **bad})
    assert r.status_code == 422, r.text


def test_name_is_required_on_save_and_error_names_the_field():
    r = client.post("/api/profile", json={"name": "  ", "skills": []})
    assert r.status_code == 422 and r.json()["detail"][0]["field"] == "name"


def test_level_zero_and_missing_normalise_to_null_never_zero():
    p = save(skills=[sk("A", level=0), sk("B"), sk("C", level=None), sk("D", level=""), sk("E", level="8"), sk("F", level=10)])
    assert [s["level"] for s in p["skills"]] == [None, None, None, None, 8, 10]
    loaded = client.get(f"/api/profile/{p['candidate_id']}").json()
    assert [s["level"] for s in loaded["skills"]] == [None, None, None, None, 8, 10]


def test_defaults_fill_optional_skill_fields_and_extensions_survive():
    p = save(skills=[{"skill_name": "Go", "evidence_basis": "quote", "source": "resume"}])
    s = p["skills"][0]
    assert s["category_code"] == "OTHER" and s["confidence"] == "low" and s["evidence"] == "" and s["level"] is None
    assert s["evidence_basis"] == "quote" and s["source"] == "resume"


def test_lists_are_cleaned_and_deduplicated():
    p = save(hackathons=["  SIH   2024 ", "sih 2024", "", "Other"])
    assert p["hackathons"] == ["SIH 2024", "Other"]


def test_talent_check_and_match_accept_validated_profile_with_null_levels():
    p = save(skills=[sk("Python", level=None)])
    assert client.post("/api/talent-check", json={"profile": p, "company_id": 4}).status_code == 200
    assert client.post("/api/skill-match", json={"profile": p, "job": {"required_skills": ["Python"]}}).status_code == 200
    assert client.post("/api/talent-check", json={"profile": {"name": "x", "skills": [sk(level=99)]}, "company_id": 4}).status_code == 422


# ------------------------------------------------------------------ D4c persistence (local file)
def test_local_mode_is_labelled_honestly():
    r = client.post("/api/profile", json={"name": "A"}).json()
    assert r["storage"] == "local-file" and "restart" not in r["warning"].lower().replace("local file", "")
    assert client.get("/api/health").json()["storage_mode"] == "local-file"


def _run_child(code, store_dir):
    env = {**os.environ, "PROFILE_STORE_DIR": str(store_dir)}
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY"):
        env.pop(k, None)
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60)


def test_save_restart_load_in_separate_processes(tmp_path):
    store = tmp_path / "durable"
    save_code = ("from fastapi.testclient import TestClient; from app import app; c=TestClient(app);"
                 "r=c.post('/api/profile',json={'name':'Restart Test','email':'r@example.com','hackathons':['H1'],"
                 "'skills':[{'skill_name':'Python','category_code':'COD','level':6}]});"
                 "print(r.json()['profile']['candidate_id'])")
    a = _run_child(save_code, store)
    assert a.returncode == 0, a.stderr[-800:]
    cid = a.stdout.strip().splitlines()[-1]
    load_code = ("import json; from fastapi.testclient import TestClient; from app import app; c=TestClient(app);"
                 f"r=c.get('/api/profile/{cid}'); print(r.status_code); print(json.dumps(r.json()))")
    b = _run_child(load_code, store)               # a brand-new Python process == a restarted backend
    assert b.returncode == 0, b.stderr[-800:]
    lines = b.stdout.strip().splitlines()
    assert lines[-2] == "200"
    data = json.loads(lines[-1])
    assert data["name"] == "Restart Test" and data["hackathons"] == ["H1"] and data["skills"][0]["level"] == 6


def test_unknown_id_is_404_and_unsafe_ids_are_400_and_cannot_escape(tmp_path):
    assert client.get("/api/profile/doesnotexist").status_code == 404
    for bad in ["a.b", "..", "a%2F..%2Fb", "x" * 65, "a b"]:
        assert client.get(f"/api/profile/{bad}").status_code in (400, 404), bad
    assert client.get("/api/profile/a.b").status_code == 400
    store = FileProfileStore(tmp_path / "s")
    with pytest.raises(ValueError):
        store.save({"candidate_id": "../escape"})
    assert not (tmp_path / "escape.json").exists()


def test_atomic_write_keeps_old_profile_if_save_crashes(tmp_path, monkeypatch):
    store = FileProfileStore(tmp_path / "s")
    store.save({"candidate_id": "abc", "name": "old"})
    def boom(*a, **k): raise OSError("disk full")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.save({"candidate_id": "abc", "name": "new"})
    monkeypatch.undo()
    assert store.get("abc")["name"] == "old"
    assert [p.name for p in (tmp_path / "s").iterdir()] == ["abc.json"]  # no temp litter


def test_unwritable_store_returns_503_not_a_fake_success(tmp_path, monkeypatch):
    blocker = tmp_path / "file-not-dir"; blocker.write_text("x")
    monkeypatch.setenv("PROFILE_STORE_DIR", str(blocker / "sub"))
    r = client.post("/api/profile", json={"name": "A"})
    assert r.status_code == 503 and "PROFILE_STORE_DIR" in r.json()["detail"]


# ------------------------------------------------------------------ D4c persistence (Supabase, real adapter + fake PostgREST)
class FakePostgrest:
    def __init__(self, fail_status=None):
        self.rows, self.calls, self.fail_status = {}, [], fail_status

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append((method, url, dict(params or {}), headers))
        class R:
            def __init__(s, status, body=None): s.status_code, s._b = status, body; s.content = b"x" if body is not None else b""
            def raise_for_status(s):
                if s.status_code >= 400:
                    import requests; raise requests.HTTPError(f"{s.status_code}", response=s)
            def json(s): return s._b
        if self.fail_status:
            return R(self.fail_status, {"message": "nope"})
        assert url.endswith("/rest/v1/radix_candidate_profiles")
        if method == "POST":
            assert (params or {}).get("on_conflict") == "candidate_id"
            import json as _j  # a real DB serialises: never alias the caller's object
            self.rows[json["candidate_id"]] = _j.loads(_j.dumps(json["profile"]))
            return R(201)
        cid = params["candidate_id"].removeprefix("eq.")
        import json as _j
        return R(200, [{"profile": _j.loads(_j.dumps(self.rows[cid]))}] if cid in self.rows else [])


@pytest.fixture
def supabase(monkeypatch):
    fake = FakePostgrest()
    monkeypatch.setattr(app_module.STORE, "url", "https://example.supabase.co")
    monkeypatch.setattr(app_module.STORE, "key", "SECRET-SERVICE-KEY-123")
    import requests
    monkeypatch.setattr(requests, "request", fake)
    return fake


def test_supabase_save_then_load_without_any_process_cache(supabase):
    p = save(hackathons=["H1"])
    assert client.get("/api/health").json()["storage_mode"] == "supabase"
    assert not hasattr(app_module, "PROFILES")                       # the old masking dict is gone
    supabase.rows[p["candidate_id"]]["name"] = "Changed In Database"  # change behind the app's back
    assert client.get(f"/api/profile/{p['candidate_id']}").json()["name"] == "Changed In Database"  # nothing masks the DB
    assert client.get("/api/profile/missing-id").status_code == 404


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_supabase_failures_are_503_and_never_leak_the_key(supabase, status):
    supabase.fail_status = status
    for r in (client.post("/api/profile", json={"name": "A"}), client.get("/api/profile/abc")):
        assert r.status_code == 503
        assert "SECRET-SERVICE-KEY-123" not in r.text and "example.supabase.co" not in r.text


# ------------------------------------------------------------------ edit tracking
def test_changed_fields_become_user_edited_and_removed_items_become_dismissed():
    p = save(name="Original", hackathons=["A", "B"], skills=[sk("Python", level=5), sk("Java")])
    p2 = save(candidate_id=p["candidate_id"], name="Edited", hackathons=["A"], skills=[sk("Python", level=5)])
    assert "name" in p2["user_edited"] and "email" not in p2["user_edited"]
    assert p2["dismissed"]["hackathons"] == ["b"] and p2["dismissed"]["skills"] == ["java|COD"]
    p3 = save(candidate_id=p["candidate_id"], name="Edited", hackathons=["A", "B"], skills=[sk("Python", level=5)])
    assert "hackathons" not in p3["dismissed"]  # re-adding clears the dismissal


# ------------------------------------------------------------------ D4b merge-not-overwrite
PARSED = {"name": "Parsed Name", "email": "parsed@example.com", "education": "B.Tech CSE", "cv_file": "resume.pdf",
          "hackathons": ["SIH 2024"], "projects": ["API"], "certifications": ["AWS CCP"],
          "skills": [sk("Python", evidence="NEW evidence", evidence_basis="quote"), sk("Docker", "CLOUD", evidence_basis="quote")]}


def test_reparse_never_overwrites_edited_fields_or_levels():
    cur = {"name": "My Preferred Name", "email": "", "user_edited": ["name"], "hackathons": ["My Own Hackathon"],
           "skills": [sk("Python", level=8, source="manual"), sk("Rust", "COD", level=3, source="manual")]}
    merged, rep = merge_resume_into_profile(cur, PARSED)
    assert merged["name"] == "My Preferred Name" and "name" in rep["kept_user_fields"]
    assert merged["email"] == "parsed@example.com" and merged["education"] == "B.Tech CSE"   # empty fields are filled
    assert merged["hackathons"] == ["My Own Hackathon", "SIH 2024"]
    by = {s["skill_name"]: s for s in merged["skills"]}
    assert by["Python"]["level"] == 8 and by["Python"]["evidence"] == "Built Python apps"     # manual skill untouched
    assert by["Rust"]["level"] == 3                                                           # never deleted
    assert by["Docker"]["level"] is None and by["Docker"]["source"] == "resume"
    assert rep["skills_kept_manual"] == 1 and rep["skills_added"] == 1


def test_resume_sourced_skill_refreshes_evidence_but_keeps_level():
    cur = {"name": "A", "skills": [sk("Python", level=6, source="resume", evidence_basis="repaired_from_text")]}
    merged, rep = merge_resume_into_profile(cur, PARSED)
    s = next(x for x in merged["skills"] if x["skill_name"] == "Python")
    assert s["evidence"] == "NEW evidence" and s["evidence_basis"] == "quote" and s["level"] == 6
    assert rep["skills_refreshed"] == 1


def test_dismissed_items_are_not_re_added():
    cur = {"name": "A", "dismissed": {"hackathons": ["sih 2024"], "skills": ["docker|CLOUD"]}}
    merged, rep = merge_resume_into_profile(cur, PARSED)
    assert merged["hackathons"] == [] and all(s["skill_name"] != "Docker" for s in merged["skills"])
    assert rep["skipped_dismissed"] == 2


def test_merge_is_idempotent_and_dedupes():
    once, _ = merge_resume_into_profile({"name": "A"}, PARSED)
    twice, rep = merge_resume_into_profile(once, PARSED)
    assert once["skills"] == [s for s in twice["skills"]] or {s["skill_name"] for s in once["skills"]} == {s["skill_name"] for s in twice["skills"]}
    assert len(twice["skills"]) == len(once["skills"]) and twice["hackathons"] == once["hackathons"]
    assert rep["skills_added"] == 0 and rep["added"] == {}


def test_merge_into_empty_profile_and_ignores_garbage_parsed_skills():
    merged, rep = merge_resume_into_profile(None, {**PARSED, "skills": [{"nope": 1}, sk("Git", "SWE"), {"skill_name": "X", "category_code": "BAD"}]})
    assert [s["skill_name"] for s in merged["skills"]] == ["Git"] and merged["field_sources"]["name"] == "resume"


def test_merge_endpoint_reports_and_does_not_save(tmp_path):
    r = client.post("/api/profile/merge-resume", json={"profile": {"name": "Mine", "user_edited": ["name"]}, "parsed": PARSED})
    assert r.status_code == 200
    assert r.json()["profile"]["name"] == "Mine" and r.json()["report"]["kept_user_fields"] == ["name"]
    assert not (tmp_path / "profiles").exists()
    assert client.post("/api/profile/merge-resume", json={"profile": {"email": "bad"}, "parsed": PARSED}).status_code == 422


def test_save_after_manual_edit_then_reparse_end_to_end(monkeypatch):
    """Parse -> merge -> save -> user edits name + sets a level -> re-parse -> merge -> edits survive -> talent check works."""
    GeminiMock(raw_text=json.dumps(good_model_output())).install(monkeypatch)
    parsed = client.post("/api/parse-resume", files={"file": ("resume.docx", resume_docx())}).json()["profile"]
    merged, _ = merge_resume_into_profile(None, parsed)
    first = client.post("/api/profile", json=merged).json()["profile"]
    edited = dict(first); edited["name"] = "Nickname"
    edited["skills"] = [{**s, "level": 7} if s["skill_name"] == "Python" else s for s in first["skills"]]
    second = client.post("/api/profile", json=edited).json()["profile"]
    assert "name" in second["user_edited"]
    stored = client.get(f"/api/profile/{second['candidate_id']}").json()
    again = client.post("/api/profile/merge-resume", json={"profile": stored, "parsed": parsed}).json()["profile"]
    assert again["name"] == "Nickname"
    assert next(s for s in again["skills"] if s["skill_name"] == "Python")["level"] == 7
    assert client.post("/api/talent-check", json={"profile": again, "company_id": 4}).status_code == 200


# ------------------------------------------------------------------ migration review (static)
def test_migrations_are_idempotent_and_locked_down():
    import re
    mig = sorted((BACKEND.parent / "supabase" / "migrations").glob("*.sql"))
    base = (BACKEND.parent / "supabase" / "migrations" / "20261028_radix_persistence.sql").read_text()
    assert len(mig) >= 3
    for f in mig:
        sql = f.read_text().lower()
        for stmt in re.findall(r"create table[^;(]*", sql):
            assert "if not exists" in stmt, f"{f.name}: non-idempotent create table"
    tables = re.findall(r"create table if not exists public\.(radix_\w+)", base)
    assert set(tables) == {"radix_candidate_profiles", "radix_talent_check_results", "radix_skill_match_results"}
    for t in tables:
        assert f"alter table public.{t} enable row level security" in base          # RLS on
        assert re.search(rf"revoke all on public\.{t} from anon, authenticated", base)  # no public access
        assert re.search(rf"grant [a-z, ]+ on public\.{t} to service_role", base)       # backend only
    fix = (BACKEND.parent / "supabase" / "migrations" / "20261029_radix_persistence_fixes.sql").read_text().lower()
    assert "drop not null" in fix and "add column if not exists" in fix
