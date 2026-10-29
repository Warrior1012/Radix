"""Role 5 Skill Matching: pure engine tests (no FastAPI). Includes ports of the original engine.test.ts cases. Phase 6."""
import json
import tempfile
from pathlib import Path
import pytest
from radix_jd.skill_match import compute_skill_match, canonical, clean
from radix_jd.jd_store import FileJDStore, InvalidJDId, jd_from_row


def job(req, pref=()):
    return {"job_id": "j1", "required_skills": list(req), "preferred_skills": list(pref)}


# ---- ports of engine.test.ts ----
def test_weights_required_2_preferred_1_rounded_2dp():
    r = compute_skill_match(["python"], job(["Python", "SQL", "AWS"], ["Docker"]))
    assert r["points"] == {"earned": 2, "possible": 7} and r["match_score"] == 28.57


def test_preferred_only_match_earns_1_point():
    assert compute_skill_match(["Docker"], job(["Python"], ["Docker"]))["match_score"] == 33.33


def test_aliases_js_ts_postgres():
    assert compute_skill_match(["js", "TS", "postgres"], job(["JavaScript", "TypeScript", "PostgreSQL"]))["match_score"] == 100


def test_unable_to_calculate_without_requirements():
    r = compute_skill_match(["Python"], job([]))
    assert r["status"] == "unable_to_calculate" and r["match_score"] is None and r["score_label"] == "Unable to calculate"
    assert r["exact_only_score"] is None


def test_no_substring_match_java_vs_javascript():
    r = compute_skill_match(["JavaScript"], job(["Java"]))
    assert r["match_score"] == 0 and canonical("Java") != canonical("JavaScript")


def test_dedupes_candidate_skills_and_required_gaps_first():
    r = compute_skill_match(["Python", "python", " PYTHON "], job(["Python", "SQL"], ["Docker"]))
    assert r["points"]["earned"] == 2 and [g["skill"] for g in r["recommendations"]] == ["SQL", "Docker"]


# ---- new behaviour ----
def test_match_types_exact_alias_fuzzy_are_reported():
    r = compute_skill_match(["Python", "js", "Kubernates"], job(["python", "JavaScript", "Kubernetes"]))
    by = {d["skill"]: d for d in r["match_details"]}
    assert by["python"]["match_type"] == "exact" and by["JavaScript"]["match_type"] == "alias"
    assert by["Kubernetes"]["match_type"] == "fuzzy" and by["Kubernetes"]["matched_with"] == "Kubernates" and by["Kubernetes"]["similarity"] >= 0.88
    assert r["match_score"] == 100 and r["exact_only_score"] == 66.67
    assert r["fuzzy_matches"][0]["skill"] == "Kubernetes"


def test_fuzzy_can_be_switched_off():
    r = compute_skill_match(["Kubernates"], job(["Kubernetes"]), fuzzy=False)
    assert r["match_score"] == 0 and r["fuzzy_matches"] == []


@pytest.mark.parametrize("cand,wanted", [
    ("Java", "JavaScript"), ("JavaScript", "TypeScript"), ("MySQL", "PostgreSQL"), ("Python2", "Python3x"),
    ("Mongoose", "MongoDB"), ("C", "C++"), ("React Native", "React"), ("Spring", "Spring Boot"), ("Vue", "Vuex"),
    ("Azure", "Aws"), ("Docker", "Dockerfile"),
])
def test_fuzzy_never_links_different_skills(cand, wanted):
    assert compute_skill_match([cand], job([wanted]))["matched_skills"] == []


def test_fuzzy_category_guard_blocks_cross_category_pairs():
    cand = [{"skill_name": "Analytic", "category_code": "SQL"}]
    j = {**job(["Analytics"]), "skills": [{"skill_name": "Analytics", "category_code": "AI"}]}
    assert compute_skill_match(cand, j)["matched_skills"] == []
    j2 = {**job(["Analytics"]), "skills": [{"skill_name": "Analytics", "category_code": "SQL"}]}
    assert compute_skill_match(cand, j2)["matched_skills"] == ["Analytics"]


def test_contract_keys_matched_and_missing_lists():
    r = compute_skill_match(["Python"], job(["Python", "SQL"], ["Docker"]))
    assert r["matched_skills"] == ["Python"] and r["missing_skills"] == ["SQL", "Docker"]
    assert r["matched_required_skills"] == ["Python"] and r["missing_preferred_skills"] == ["Docker"]


def test_gap_explanations_carry_points_lost_and_priority():
    r = compute_skill_match([], job(["SQL"], ["Docker"]))      # possible = 3
    sql, docker = r["gaps"]
    assert (sql["priority"], sql["points_lost"], sql["score_impact_percent"]) == ("high", 2, 66.67)
    assert (docker["priority"], docker["points_lost"], docker["score_impact_percent"]) == ("medium", 1, 33.33)
    assert "required" in sql["why"] and "2 of 3 points" in sql["why"] and "preferred" in docker["why"]
    assert sum(g["points_lost"] for g in r["gaps"]) == r["points"]["possible"] - r["points"]["earned"]


def test_skill_in_both_lists_counts_once_as_required():
    r = compute_skill_match(["Python"], job(["Python"], ["python", "Docker"]))
    assert r["points"] == {"earned": 2, "possible": 3}


def test_accepts_skill_dicts_and_ignores_blank_names():
    r = compute_skill_match([{"skill_name": "Python"}, {"skill_name": ""}, {"skill_name": None}, "  "], job(["Python"]))
    assert r["match_score"] == 100


def test_different_candidates_get_different_scores():
    j = job(["Python", "SQL", "Docker"], ["AWS"])
    a = compute_skill_match(["Python", "SQL", "Docker", "AWS"], j)["match_score"]
    b = compute_skill_match(["Python"], j)["match_score"]
    c = compute_skill_match([], j)["match_score"]
    assert a == 100 and b == 28.57 and c == 0


def test_deterministic_and_does_not_mutate_inputs():
    cand, j = ["Python", "js"], job(["Python", "JavaScript", "SQL"], ["Docker"])
    before = json.dumps([cand, j], sort_keys=True)
    assert compute_skill_match(cand, j) == compute_skill_match(cand, j)
    assert json.dumps([cand, j], sort_keys=True) == before


def test_alias_map_ported_from_original_engine():
    for a, b in [("k8s", "Kubernetes"), ("Amazon Web Services", "AWS"), ("React.js", "react"), ("C Sharp", "C#"), ("Golang", "Go"),
                 ("ci cd", "CI/CD"), ("Natural Language Processing", "NLP"), ("RESTful API", "REST")]:
        assert canonical(a) == canonical(b), (a, b)
    assert clean("  A   B ") == "a b"


# ---- JD store ----
def test_jd_store_roundtrip_in_a_fresh_instance_and_id_validation():
    with tempfile.TemporaryDirectory() as d:
        jd = {"jd_id": "abc-123", "required_skills": ["Python"], "preferred_skills": []}
        FileJDStore(Path(d)).save(jd)
        assert FileJDStore(Path(d)).get("abc-123") == jd          # new instance = "restart"
        assert FileJDStore(Path(d)).get("nope") is None
        for bad in ("../x", "a/b", "", "x" * 65, "a b"):
            with pytest.raises(InvalidJDId):
                FileJDStore(Path(d)).get(bad)


def test_jd_from_row_defaults_missing_requirement_type_to_required():
    jd = jd_from_row({"id": "r1", "source_file": "a.pdf", "skills": [
        {"skill_name": "Python"}, {"skill_name": "Docker", "requirement_type": "preferred"}, {"skill_name": ""}, "junk"]})
    assert jd["jd_id"] == "r1" and jd["required_skills"] == ["Python"] and jd["preferred_skills"] == ["Docker"]


def test_descriptive_jd_phrases_match_atomic_resume_skills():
    candidate = ["Python", "FastAPI", "SQL", "Git", "pytest", "PostgreSQL", "Docker", "TypeScript", "React", "CI/CD", "Redis"]
    result = compute_skill_match(candidate, job(
        ["Automated testing with pytest", "FastAPI or REST API development", "Git version control",
         "Problem solving and data structures", "Python programming", "SQL and relational databases"],
        ["Docker and containerisation", "PostgreSQL", "TypeScript or React fundamentals", "CI/CD pipelines", "Redis caching"],
    ))
    assert result["counts"] == {"matched_required": 5, "missing_required": 1, "matched_preferred": 5, "missing_preferred": 0}
    assert result["match_score"] == 88.24
    assert result["missing_required_skills"] == ["Problem solving and data structures"]
    by_skill = {d["skill"]: d for d in result["match_details"]}
    assert by_skill["Python programming"]["matched_with"] == "Python"
    assert by_skill["FastAPI or REST API development"]["matched_with"] == "FastAPI"
    assert by_skill["Automated testing with pytest"]["matched_with"] == "pytest"
    assert by_skill["Python programming"]["match_type"] == "phrase"


def test_phrase_aliases_do_not_turn_java_into_javascript():
    result = compute_skill_match(["JavaScript"], job(["Java"]))
    assert result["matched_skills"] == []


def test_postgres_implies_generic_sql_database_requirement_with_partial_credit():
    result = compute_skill_match(
        [{"skill_name": "PostgreSQL", "category_code": "SQL", "evidence": "Built a project using PostgreSQL", "confidence": "high"}],
        {"required_skills": ["SQL databases"], "preferred_skills": [],
         "skills": [{"skill_name": "SQL databases", "category_code": "SQL", "requirement_type": "required"}]},
    )
    detail = result["match_details"][0]
    assert detail["matched"] is True
    assert detail["match_type"] == "implied"
    assert detail["evidence_quote"] == "Built a project using PostgreSQL"
    assert detail["points_earned"] == 1.5
    assert result["match_score"] == 75.0
    assert result["gaps"] == []


def test_sql_does_not_imply_experience_with_a_specific_database_engine():
    result = compute_skill_match(
        [{"skill_name": "SQL", "category_code": "SQL", "evidence": "Practised SQL joins", "confidence": "high"}],
        {"required_skills": ["PostgreSQL"], "preferred_skills": [],
         "skills": [{"skill_name": "PostgreSQL", "category_code": "SQL", "requirement_type": "required"}]},
    )
    assert result["match_details"][0]["matched"] is False
    assert result["match_score"] == 0.0
