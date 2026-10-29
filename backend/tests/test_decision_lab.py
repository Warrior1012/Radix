from __future__ import annotations

import pytest

from radix_jd.decision_lab import build_proof_graph, simulate_skill_match


JOB = {
    "required_skills": ["Python", "FastAPI"],
    "preferred_skills": ["Docker"],
    "skills": [
        {"skill_name": "Python", "category_code": "COD"},
        {"skill_name": "FastAPI", "category_code": "SWE"},
        {"skill_name": "Docker", "category_code": "CLOUD"},
    ],
}


def test_proof_graph_distinguishes_level_evidence_claim_and_missing_requirement():
    profile = [
        {"skill_name": "Python", "category_code": "COD", "evidence": "Built a Python API", "confidence": "high", "level": 7},
        {"skill_name": "FastAPI", "category_code": "SWE", "evidence": "Used FastAPI for routing", "confidence": "medium", "level": None},
        {"skill_name": "Docker", "category_code": "CLOUD", "evidence": "", "confidence": "low", "level": None},
    ]

    result = build_proof_graph(profile, JOB)
    by_skill = {row["skill"]: row for row in result["requirements"]}

    assert by_skill["Python"]["status"] == "level_entered"
    assert by_skill["Python"]["candidate_level"] == 7
    assert by_skill["FastAPI"]["status"] == "evidence_available"
    assert by_skill["Docker"]["status"] == "claimed"


def test_proof_graph_marks_missing_requirement_unassessed():
    result = build_proof_graph(
        [{"skill_name": "Python", "category_code": "COD", "evidence": "Python work", "level": None}],
        JOB,
    )
    by_skill = {row["skill"]: row for row in result["requirements"]}
    assert by_skill["FastAPI"]["status"] == "unassessed"
    assert result["summary"]["required_unassessed"] == 1


def test_simulator_increases_score_for_a_missing_required_skill_without_mutating_profile():
    profile = [
        {"skill_name": "Python", "category_code": "COD", "evidence": "Built a Python API", "level": None}
    ]
    original = [dict(item) for item in profile]

    result = simulate_skill_match(profile, JOB, ["FastAPI"])

    assert result["hypothetical"] is True
    assert result["persisted"] is False
    assert result["baseline_score"] == 40.0
    assert result["scenario_score"] == 80.0
    assert result["score_delta"] == 40.0
    assert profile == original
    assert "FastAPI" not in [s["skill_name"] for s in profile]


def test_simulator_rejects_skills_that_are_not_missing_requirements():
    profile = [{"skill_name": "Python", "category_code": "COD", "evidence": "Python work", "level": 3}]
    with pytest.raises(ValueError, match="not a currently missing requirement"):
        simulate_skill_match(profile, JOB, ["Python"])


def test_simulator_deduplicates_selected_requirements():
    profile = [{"skill_name": "Python", "category_code": "COD", "evidence": "", "level": None}]
    result = simulate_skill_match(profile, JOB, ["FastAPI", "FastAPI"])
    assert result["assumed_skills"] == ["FastAPI"]
