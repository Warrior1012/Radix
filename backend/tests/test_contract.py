"""Shared-contract tests (Phase 1). xfail(strict=True) = known open defect from PROJECT_STATE.md;
when the defect is fixed the test XPASSes, which fails the run until the marker is removed."""
import pytest
from fastapi.testclient import TestClient
from app import app
from radix_jd.contract import CATEGORIES, RADIX_CATEGORY_CODES, SKILL_CATEGORY_CODES, TalentCheckResult, SkillMatchResult
from radix_jd.talent_check import compute_talent_check
from radix_jd import schemas

client = TestClient(app)


def test_twelve_categories_plus_other():
    assert len(CATEGORIES) == 12 and len(RADIX_CATEGORY_CODES) == 12
    assert RADIX_CATEGORY_CODES == {"COD", "DSA", "OOD", "APTI", "COMM", "AI", "CLOUD", "SQL", "SWE", "SYSD", "NETW", "OS"}
    assert SKILL_CATEGORY_CODES == RADIX_CATEGORY_CODES | {"OTHER"}
    assert schemas.CATEGORY_CODES == SKILL_CATEGORY_CODES  # one source of truth


def test_talent_check_output_matches_official_contract():
    r = client.post("/api/talent-check", json={"profile": {"name": "C", "skills": [{"skill_name": "Python", "category_code": "COD", "level": 7}]}, "company_id": 4})
    assert r.status_code == 200
    TalentCheckResult.model_validate(r.json())


@pytest.mark.parametrize("company_id", [4, 78, 24])
def test_all_three_snapshot_companies_cover_all_12_categories(company_id):
    rows = client.post("/api/talent-check", json={"profile": {"skills": []}, "company_id": company_id}).json()["skillset_gap"]
    assert sorted(x["category_code"] for x in rows) == sorted(RADIX_CATEGORY_CODES)
    assert all(1 <= x["required_level"] <= 10 for x in rows)


def test_positional_levels_list_is_never_used_for_joins():
    """A company whose deprecated positional `levels` is scrambled must still score by category_code."""
    by_code = {c: 5 for c, _ in CATEGORIES}
    by_code["SQL"] = 9
    company = {"levels_by_code": by_code, "levels": list(reversed([by_code[c] for c, _ in CATEGORIES]))}
    rows = {r["category_code"]: r for r in compute_talent_check([], company)["skillset_gap"]}
    assert rows["SQL"]["required_level"] == 9 and rows["CLOUD"]["required_level"] == 5


def test_missing_category_in_benchmark_is_rejected_not_defaulted():
    with pytest.raises(ValueError):
        compute_talent_check([], {"levels_by_code": {"COD": 5}})


def test_skill_match_output_matches_official_contract():
    r = client.post("/api/skill-match", json={"profile": {"skills": [{"skill_name": "Python"}]}, "job": {"job_id": "x", "required_skills": ["Python", "SQL"]}})
    assert r.status_code == 200, r.text
    SkillMatchResult.model_validate(r.json())


def test_unassessed_categories_are_not_scored_as_inability():
    rows = client.post("/api/talent-check", json={"profile": {"skills": []}, "company_id": 4}).json()
    assert rows["readiness_score"] is None and rows["skillset_gap"][0]["status"] == "unassessed" and rows["skillset_gap"][0]["candidate_level"] is None


def test_no_duplicate_route_registrations():
    """A stale copy of a handler once sat behind the live one (first-registered wins), so tests passed against code that was not what the module exported."""
    import app as appmod
    seen = {}
    for r in appmod.app.routes:
        for m in getattr(r, 'methods', None) or ():
            key = (m, r.path)
            seen[key] = seen.get(key, 0) + 1
    dups = sorted(k for k, n in seen.items() if n > 1)
    assert not dups, f'duplicate routes registered: {dups}'


def test_app_module_has_one_definition_per_handler():
    import re, pathlib
    src = (pathlib.Path(__file__).resolve().parent.parent / 'app.py').read_text()
    names = re.findall(r'^(?:async )?def (\w+)\(', src, flags=re.M)
    dups = sorted({n for n in names if names.count(n) > 1})
    assert not dups, f'function defined more than once in app.py: {dups}'
