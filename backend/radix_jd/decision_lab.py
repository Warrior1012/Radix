"""Additive, stateless helpers for the RADIX Decision Lab.

ProofGraph reports what the supplied profile currently supports. The what-if simulator
runs a deterministic scenario against missing JD requirements in memory only; it never
writes to the profile repository or result tables.
"""
from __future__ import annotations

from typing import Any

from .skill_match import canonical, compute_skill_match


def _skill_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("skill_name") or "").strip()
    return str(item or "").strip()


def _valid_level(item: dict[str, Any] | None) -> int | None:
    if not isinstance(item, dict):
        return None
    raw = item.get("level")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        level = int(raw)
    except (TypeError, ValueError):
        return None
    return level if 1 <= level <= 10 else None


def _profile_status(item: dict[str, Any] | None) -> str:
    """A level is explicit user-entered data, not proof of an independent skills test."""
    if not isinstance(item, dict):
        return "unassessed"
    if _valid_level(item) is not None:
        return "level_entered"
    if str(item.get("evidence") or "").strip():
        return "evidence_available"
    return "claimed"


def _candidate_for(label: str | None, skills: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not label:
        return None
    key = canonical(label)
    return next((s for s in skills if canonical(_skill_name(s)) == key), None)


def _job_requirements(job: dict[str, Any]) -> list[str]:
    required = list(job.get("required_skills") or [])
    preferred = list(job.get("preferred_skills") or [])
    seen: set[str] = set()
    out: list[str] = []
    for raw in required + preferred:
        name = str(raw or "").strip()
        key = canonical(name)
        if name and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def build_proof_graph(candidate_skills: list[Any], job: dict[str, Any]) -> dict[str, Any]:
    """Join JD requirements to current candidate skills and describe evidence state."""
    skills = [s for s in candidate_skills or [] if isinstance(s, dict) and _skill_name(s)]
    match = compute_skill_match(skills, job)
    rows: list[dict[str, Any]] = []
    for detail in match.get("match_details", []):
        candidate = _candidate_for(detail.get("matched_with"), skills)
        status = _profile_status(candidate) if detail.get("matched") else "unassessed"
        rows.append({
            "skill": detail.get("skill"),
            "requirement_type": detail.get("requirement_type"),
            "required": detail.get("requirement_type") == "required",
            "matched": bool(detail.get("matched")),
            "matched_with": detail.get("matched_with"),
            "status": status,
            "candidate_level": _valid_level(candidate),
            "evidence": str((candidate or {}).get("evidence") or ""),
            "confidence": str((candidate or {}).get("confidence") or "low"),
            "match_type": detail.get("match_type"),
            "points_lost": detail.get("points_lost", 0),
        })

    profile_rows = []
    for skill in skills:
        status = _profile_status(skill)
        profile_rows.append({
            "skill_name": _skill_name(skill),
            "category_code": str(skill.get("category_code") or "OTHER"),
            "status": status,
            "level": _valid_level(skill),
            "evidence": str(skill.get("evidence") or ""),
            "confidence": str(skill.get("confidence") or "low"),
            "source": str(skill.get("source") or "unknown"),
        })

    status_counts = {key: sum(1 for row in rows if row["status"] == key)
                     for key in ("level_entered", "evidence_available", "claimed", "unassessed")}
    required_rows = [row for row in rows if row["required"]]
    preferred_rows = [row for row in rows if not row["required"]]
    return {
        "match_score": match.get("match_score"),
        "status": match.get("status"),
        "requirements": rows,
        "profile_skills": profile_rows,
        "summary": {
            "requirements": len(rows),
            "required": len(required_rows),
            "preferred": len(preferred_rows),
            "required_unassessed": sum(1 for row in required_rows if row["status"] == "unassessed"),
            "profile_skills": len(profile_rows),
            "status_counts": status_counts,
        },
        "methodology": (
            "Requirements are compared with the submitted profile using the deterministic RADIX matcher. "
            "A skill level is shown only when an explicit 1-10 level is present; it is not inferred from a resume. "
            "Evidence text is supporting material, not independent verification. Missing profile matches are unassessed."
        ),
    }


def simulate_skill_match(candidate_skills: list[Any], job: dict[str, Any],
                         assumed_skills: list[str]) -> dict[str, Any]:
    """Calculate a no-persistence 'what if these missing requirements were demonstrated?' scenario."""
    skills = [dict(s) for s in (candidate_skills or []) if isinstance(s, dict) and _skill_name(s)]
    baseline = compute_skill_match(skills, job)
    missing = list(baseline.get("missing_skills") or [])
    missing_by_key = {canonical(name): name for name in missing}
    selected: list[str] = []
    for raw in assumed_skills or []:
        key = canonical(str(raw or "").strip())
        actual = missing_by_key.get(key)
        if not actual:
            raise ValueError(f"{raw!r} is not a currently missing requirement for this job.")
        if actual not in selected:
            selected.append(actual)

    category_by_key = {
        canonical(str(item.get("skill_name") or "")): str(item.get("category_code") or "OTHER")
        for item in (job.get("skills") or [])
        if isinstance(item, dict)
    }
    scenario_skills = [dict(s) for s in skills]
    for name in selected:
        scenario_skills.append({
            "skill_name": name,
            "category_code": category_by_key.get(canonical(name), "OTHER"),
            "evidence": "",
            "confidence": "low",
            "level": None,
            "source": "hypothetical",
        })

    scenario = compute_skill_match(scenario_skills, job)
    before = baseline.get("match_score")
    after = scenario.get("match_score")
    return {
        "hypothetical": True,
        "persisted": False,
        "assumed_skills": selected,
        "baseline_score": before,
        "scenario_score": after,
        "score_delta": round(after - before, 2) if before is not None and after is not None else None,
        "baseline": baseline,
        "scenario": scenario,
        "assumption_note": (
            "Selected gaps are treated as demonstrated only for this calculation. No evidence, proficiency level, "
            "profile field, or saved result is created or changed."
        ),
    }
