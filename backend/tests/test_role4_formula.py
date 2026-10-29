"""Role 4 Talent Check: pure formula tests (no FastAPI needed). Phase 5."""
import json
import pytest
from radix_jd.contract import CATEGORIES
from radix_jd.talent_check import compute_talent_check, required_levels_by_code, candidate_level

CODES = [c for c, _ in CATEGORIES]
FLAT5 = {"levels_by_code": {c: 5 for c in CODES}}


def S(code, level=None, name=None, **kw):
    d = {"skill_name": name or f"{code}-skill", "category_code": code, **kw}
    if level is not None:
        d["level"] = level
    return d


def rows(result):
    return {r["category_code"]: r for r in result["skillset_gap"]}


def test_empty_profile_is_not_scored_as_zero_ability():
    r = compute_talent_check([], FLAT5)
    assert r["readiness_score"] is None and r["skills_assessed"] == 0
    assert r["readiness_floor"] == 0.0 and r["unassessed_categories"] == CODES
    assert all(x["status"] == "unassessed" and x["candidate_level"] is None and x["gap"] is None for x in r["skillset_gap"])
    assert all("not counted as zero" in x["explanation"] for x in r["skillset_gap"])


def test_unassessed_categories_do_not_drag_the_score_down():
    one = compute_talent_check([S("COD", 5)], FLAT5)
    assert one["readiness_score"] == 100.0           # only assessed category counts
    assert one["readiness_floor"] == round(100 / 12, 1)
    assert one["skills_assessed"] == 1 and one["coverage"] == round(1 / 12, 2)


def test_mean_is_over_assessed_categories_only():
    r = compute_talent_check([S("COD", 10), S("DSA", 2)], FLAT5)   # 100 and 40
    assert r["readiness_score"] == 70.0


def test_score_is_capped_at_100_per_category():
    r = compute_talent_check([S("COD", 10)], {"levels_by_code": {**FLAT5["levels_by_code"], "COD": 4}})
    assert rows(r)["COD"]["skill_score"] == 100.0 and rows(r)["COD"]["gap"] is False


def test_multiple_skills_in_one_category_use_the_highest_level_regardless_of_order():
    a = [S("COD", name="Java"), S("COD", 8, name="Python"), S("COD", 3, name="C")]
    for order in (a, list(reversed(a))):
        row = rows(compute_talent_check(order, FLAT5))["COD"]
        assert row["candidate_level"] == 8 and row["level_from_skill"] == "Python"
        assert sorted(row["skills_listed"]) == ["C", "Java", "Python"]


def test_listed_but_unlevelled_skill_is_unassessed_and_explained():
    row = rows(compute_talent_check([S("SQL", name="PostgreSQL")], FLAT5))["SQL"]
    assert row["status"] == "unassessed" and "PostgreSQL" in row["explanation"]


@pytest.mark.parametrize("bad", [0, "0", "", None, True, 11, -3, "abc", -1.0])
def test_invalid_or_zero_levels_are_unassessed_never_clamped(bad):
    row = rows(compute_talent_check([{"skill_name": "x", "category_code": "COD", "level": bad}], FLAT5))["COD"]
    assert row["candidate_level"] is None and row["status"] == "unassessed"


def test_candidate_level_helper():
    assert candidate_level(None) is None and candidate_level({"level": 0}) is None and candidate_level({"level": "7"}) == 7


@pytest.mark.parametrize("level,status", [(7, "meets_bar"), (5, "meets_bar"), (4, "close_gap"), (3, "close_gap"), (2, "priority_gap")])
def test_status_bands(level, status):
    row = rows(compute_talent_check([S("OS", level)], FLAT5))["OS"]
    assert row["status"] == status and row["gap"] is (status != "meets_bar")
    assert row["gap_detected"] == row["gap"] and row["gap_amount"] == max(5 - level, 0)


def test_other_and_unknown_categories_are_reported_not_scored():
    r = compute_talent_check([S("OTHER", 9, name="Figma"), S("ZZZ", 9, name="Mystery")], FLAT5)
    assert r["readiness_score"] is None and r["ignored_skills"] == ["Figma", "Mystery"]


def test_category_code_is_case_insensitive():
    assert rows(compute_talent_check([S("cod", 5)], FLAT5))["COD"]["candidate_level"] == 5


def test_priority_gaps_sorted_by_size_and_only_real_gaps():
    r = compute_talent_check([S("COD", 1), S("DSA", 4), S("OS", 5), S("SQL")], FLAT5)
    assert [g["category_code"] for g in r["priority_gaps"]] == ["COD", "DSA"]


def test_provisional_when_few_categories_assessed():
    thin = compute_talent_check([S("COD", 5)], FLAT5)
    assert thin["provisional"] is True and thin["readiness_label"].endswith("(provisional)")
    full = compute_talent_check([S(c, 5) for c in CODES], FLAT5)
    assert full["provisional"] is False and full["readiness_score"] == 100.0 and full["readiness_label"] == "Strong alignment"


def test_labels_thresholds():
    full = lambda lv: compute_talent_check([S(c, lv) for c in CODES], FLAT5)["readiness_label"]
    assert full(5) == "Strong alignment" and full(4) == "Strong alignment"      # 80
    assert full(3) == "Building alignment" and full(2) == "Significant gaps"     # 60 / 40


def test_deterministic_and_does_not_mutate_input():
    skills = [S("COD", 8), S("SQL", 3)]
    before = json.dumps(skills, sort_keys=True)
    assert compute_talent_check(skills, FLAT5) == compute_talent_check(skills, FLAT5)
    assert json.dumps(skills, sort_keys=True) == before


def test_benchmark_validation():
    with pytest.raises(ValueError):
        required_levels_by_code({"levels_by_code": {"COD": 5}})
    with pytest.raises(ValueError):
        required_levels_by_code({"levels_by_code": {**FLAT5["levels_by_code"], "COD": 0}})
    with pytest.raises(ValueError):
        required_levels_by_code({})


def test_different_candidates_get_visibly_different_scores_on_the_official_snapshot():
    """Brief 'definition of done': results must differ per candidate. Synthetic profiles, official benchmark."""
    import pathlib
    data = json.loads((pathlib.Path(__file__).parent.parent / "data" / "talent_check_company_skillsets.json").read_text())
    cos = {c["short_name"]: {"levels_by_code": c["skill_levels"]} for c in data["companies"]}
    systems = [S(c, 8) for c in ("COD", "OS", "NETW", "SWE", "OOD", "DSA")]
    support = [S(c, 5) for c in ("COD", "SQL", "COMM", "OS", "SWE", "OOD")]
    scores = {(who, co): compute_talent_check(p, b)["readiness_score"] for who, p in (("sys", systems), ("sup", support)) for co, b in cos.items()}
    assert scores[("sys", "Google")] != scores[("sup", "Google")]
    assert scores[("sup", "Oracle Financial Services")] > scores[("sup", "Google")]   # entry-level fits Oracle better
    assert len(set(scores.values())) > 3


@pytest.mark.parametrize("short", ["Google", "Microsoft", "Oracle Financial Services"])
def test_every_snapshot_company_covers_all_12_categories(short):
    import pathlib
    data = json.loads((pathlib.Path(__file__).parent.parent / "data" / "talent_check_company_skillsets.json").read_text())
    c = next(x for x in data["companies"] if x["short_name"] == short)
    r = compute_talent_check([], {"levels_by_code": c["skill_levels"]})
    assert [x["category_code"] for x in r["skillset_gap"]] == CODES
    assert [x["required_level"] for x in r["skillset_gap"]] == [c["skill_levels"][k] for k in CODES]


def test_readiness_verdict_requires_coverage_score_and_no_large_gap():
    no_evidence = compute_talent_check([], FLAT5)
    assert no_evidence["readiness_verdict"] == "insufficient_evidence"

    enough_strong = compute_talent_check([S(c, 8) for c in CODES[:6]], FLAT5)
    assert enough_strong["readiness_verdict"] == "ready"
    assert enough_strong["readiness_verdict_rule"]["minimum_assessed_categories"] == 6

    strong_mean_with_priority_gap = compute_talent_check([S(CODES[0], 1)] + [S(c, 10) for c in CODES[1:6]], FLAT5)
    assert strong_mean_with_priority_gap["readiness_score"] >= 80
    assert strong_mean_with_priority_gap["readiness_verdict"] == "not_ready"
