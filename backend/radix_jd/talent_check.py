"""Role 4 Talent Check: deterministic readiness calculation (no LLM).

Formula (documented in docs/CONTRACT.md, section "Talent Check formula"):

* A category's *candidate level* is the HIGHEST explicit ``level`` (1-10) among the profile's skills tagged with
  that ``category_code``. Skills with no level do not count as ability and do not lower the result (D5e).
* A category is **assessed** when at least one skill in it has a level; otherwise it is **unassessed**.
  Unassessed != zero ability: it is excluded from the score and explained (D5a).
* ``category_score = min(candidate_level / required_level, 1) * 100`` for assessed categories only.
* ``readiness_score`` = unweighted mean of the assessed category scores, or ``None`` when nothing is assessed.
* ``readiness_floor`` = the same sum divided by 12 (every unassessed category counted as 0): the worst case.
  ``score_range`` reports both so a thin profile is never presented as precise.
* Verdict rule (design decision): ``ready`` only if score >= 80, at least 6 categories are assessed,
  and no assessed category has a gap of 3+ levels. Otherwise return ``not_ready`` or ``insufficient_evidence``.
* Joins are always by ``category_code``. Skills tagged ``OTHER`` / unknown codes are reported, never scored.
"""
from __future__ import annotations

from typing import Any

from .contract import CATEGORIES

TOTAL_CATEGORIES = len(CATEGORIES)
LOW_COVERAGE_BELOW = 6  # fewer assessed categories than this => the score is labelled provisional

METHODOLOGY = (
    "Per category: candidate level = highest explicit level among that category's skills; score = "
    "min(candidate level / required level, 1) x 100. Readiness = unweighted mean over ASSESSED categories only. "
    "Categories with no entered level are 'unassessed' - they are explained, not scored as zero. "
    "readiness_floor shows the worst case if every unassessed category were zero."
)
DISCLAIMER = (
    "Competency-alignment estimate, not a hiring probability. Levels must be explicitly entered; they are never "
    "inferred from keyword presence. An unassessed category says nothing about the candidate's ability. "
    "The verdict is a transparent workflow rule, not a hiring decision."
)

READY_SCORE_THRESHOLD = 80
MIN_ASSESSED_FOR_VERDICT = 6
MAX_GAP_FOR_READY = 2


def _level_of(skill: dict[str, Any]) -> int | None:
    """Explicit proficiency 1-10, else None. 0, '', None, bools, non-numbers and out-of-range values are 'unassessed'."""
    raw = skill.get("level", skill.get("candidate_level"))
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(raw)
    except (ValueError, TypeError):
        return None
    return value if 1 <= value <= 10 else None


def candidate_level(skill: dict[str, Any] | None) -> int | None:
    """Kept for backward compatibility: level of ONE skill, or None when unassessed."""
    return _level_of(skill) if skill else None


def required_levels_by_code(company: dict[str, Any]) -> dict[str, int]:
    """Code-keyed required levels. The positional ``levels`` list is deliberately never used (misalignment risk)."""
    raw = company.get("levels_by_code") or company.get("skill_levels")
    if not isinstance(raw, dict):
        raise ValueError("Company benchmark has no code-keyed levels (levels_by_code / skill_levels)")
    by_code = {str(k).upper(): int(v) for k, v in raw.items()}
    missing = [code for code, _ in CATEGORIES if code not in by_code]
    if missing:
        raise ValueError(f"Company benchmark is missing categories: {missing}")
    bad = [code for code, _ in CATEGORIES if not 1 <= by_code[code] <= 10]
    if bad:
        raise ValueError(f"Company benchmark levels must be 1-10; bad categories: {bad}")
    return by_code


def _status(candidate: int | None, required: int) -> str:
    if candidate is None:
        return "unassessed"
    gap = required - candidate
    return "meets_bar" if gap <= 0 else ("close_gap" if gap <= 2 else "priority_gap")


def _explain(label: str, status: str, candidate: int | None, required: int, listed: list[str], best: str | None) -> str:
    if status == "unassessed":
        if listed:
            return (f"{label}: not assessed. The profile lists {', '.join(listed[:4])} here but no proficiency level has "
                    f"been entered, so this category is left out of the score (it is not counted as zero). "
                    f"Enter a 1-10 level to include it. The company bar is {required}.")
        return (f"{label}: not assessed. No skill in this category is on the profile, so it is left out of the score "
                f"(not counted as zero). The company bar is {required}.")
    via = f" (from {best})" if best else ""
    if status == "meets_bar":
        return f"{label}: level {candidate}{via} meets the company bar of {required}."
    gap = required - candidate
    word = "close to" if status == "close_gap" else "below"
    return f"{label}: level {candidate}{via} is {gap} point{'s' if gap != 1 else ''} {word} the company bar of {required}."


def compute_talent_check(skills: list[dict[str, Any]], company: dict[str, Any]) -> dict[str, Any]:
    """Score one profile's skills against one company benchmark (joined by category_code). Deterministic."""
    required_by_code = required_levels_by_code(company)
    grouped: dict[str, list[dict[str, Any]]] = {code: [] for code, _ in CATEGORIES}
    ignored: list[str] = []
    for skill in skills or []:
        code = str(skill.get("category_code", "")).strip().upper()
        if code in grouped:
            grouped[code].append(skill)
        elif skill.get("skill_name"):
            ignored.append(str(skill["skill_name"]))

    breakdown: list[dict[str, Any]] = []
    for code, label in CATEGORIES:
        in_cat = grouped[code]
        levelled = [(lv, s) for s in in_cat if (lv := _level_of(s)) is not None]
        level, best_skill = (max(levelled, key=lambda p: p[0]) if levelled else (None, None))
        required = required_by_code[code]
        status = _status(level, required)
        evidence_src = best_skill or next((s for s in in_cat if s.get("evidence")), None)
        listed = [str(s.get("skill_name")) for s in in_cat if s.get("skill_name")]
        best_name = str(best_skill.get("skill_name")) if best_skill else None
        score = None if level is None else round(min(level / required, 1) * 100, 1)
        gap_amount = None if level is None else max(required - level, 0)
        gap = None if level is None else gap_amount > 0
        breakdown.append({
            "skill_name": label, "category_code": code,
            "required_level": required, "candidate_level": level,
            "gap": gap, "gap_detected": gap, "gap_amount": gap_amount,
            "skill_score": score, "status": status,
            "assessed": level is not None,
            "skills_listed": listed, "level_from_skill": best_name,
            "evidence": evidence_src.get("evidence") if evidence_src else None,
            "confidence": (evidence_src.get("confidence", "none") if evidence_src else "none"),
            "explanation": _explain(label, status, level, required, listed, best_name),
        })

    assessed = [x for x in breakdown if x["assessed"]]
    total_points = sum(x["skill_score"] for x in assessed)
    readiness = round(total_points / len(assessed), 1) if assessed else None
    floor = round(total_points / TOTAL_CATEGORIES, 1)
    if readiness is None:
        label = "Not enough assessed skills"
    elif readiness >= 80:
        label = "Strong alignment"
    elif readiness >= 60:
        label = "Building alignment"
    else:
        label = "Significant gaps"
    provisional = len(assessed) < LOW_COVERAGE_BELOW
    if provisional and readiness is not None:
        label += " (provisional)"
    gaps = [x for x in breakdown if x["gap"]]
    large_gaps = [x for x in assessed if x.get("gap_amount") is not None and x["gap_amount"] > MAX_GAP_FOR_READY]
    if readiness is None or len(assessed) < MIN_ASSESSED_FOR_VERDICT:
        verdict = "insufficient_evidence"
        verdict_reason = f"Assess at least {MIN_ASSESSED_FOR_VERDICT} categories with explicit proficiency levels before a readiness verdict is issued."
    elif readiness >= READY_SCORE_THRESHOLD and not large_gaps:
        verdict = "ready"
        verdict_reason = f"Readiness is at least {READY_SCORE_THRESHOLD}/100, at least {MIN_ASSESSED_FOR_VERDICT} categories are assessed, and no assessed gap exceeds {MAX_GAP_FOR_READY} levels."
    else:
        verdict = "not_ready"
        if readiness < READY_SCORE_THRESHOLD:
            verdict_reason = f"Readiness is below the {READY_SCORE_THRESHOLD}/100 threshold."
        else:
            codes = ", ".join(x["category_code"] for x in large_gaps)
            verdict_reason = f"Priority gaps of 3 or more levels remain in: {codes}."
    return {
        "readiness_score": readiness,
        "readiness_label": label,
        "readiness_verdict": verdict,
        "readiness_verdict_rule": {
            "score_threshold": READY_SCORE_THRESHOLD,
            "minimum_assessed_categories": MIN_ASSESSED_FOR_VERDICT,
            "maximum_gap_for_ready": MAX_GAP_FOR_READY,
            "reason": verdict_reason,
        },
        "readiness_floor": floor,
        "score_range": {"assessed_only": readiness, "if_unassessed_were_zero": floor},
        "provisional": provisional,
        "skillset_gap": breakdown,
        "priority_gaps": sorted(gaps, key=lambda x: (-x["gap_amount"], x["skill_score"], x["category_code"]))[:4],
        "unassessed_categories": [x["category_code"] for x in breakdown if not x["assessed"]],
        "skills_assessed": len(assessed),
        "skills_total": TOTAL_CATEGORIES,
        "coverage": round(len(assessed) / TOTAL_CATEGORIES, 2),
        "ignored_skills": ignored,
        "methodology": METHODOLOGY,
        "disclaimer": DISCLAIMER,
    }
