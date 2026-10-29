"""Role 5 Skill Matching: deterministic weighted match (required=2, preferred=1) with bounded fuzzy matching.

Each JD skill is matched to the candidate's skills in three passes, and the result says which pass won:
  1. ``exact``  - same text after lower-casing / whitespace collapsing
  2. ``alias``  - same canonical id via the explicit synonym map ported from the original Role 5 engine (JS = JavaScript)
  3. ``fuzzy``  - near-identical spelling (difflib ratio >= 0.88), guarded: both names >= 5 chars, same first letter,
                  identical digits, never between two *known, different* skills, never across two different RADIX
                  categories. Never substring matching ("Java" does not match "JavaScript").
Fuzzy matches count toward the score but are flagged; ``exact_only_score`` shows the score without them.
Missing skills come with priority, points lost and a plain-language reason: the gap list matters more than the number.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from .contract import CATEGORIES

REQUIRED_WEIGHT = 2
PREFERRED_WEIGHT = 1
FUZZY_THRESHOLD = 0.88
FUZZY_MIN_LENGTH = 5
MAX_SKILL_LENGTH = 60
_RADIX_CODES = {c for c, _ in CATEGORIES}

# Explicit, defensible alias map (port of modules/source-role5/matching-engine/normalize.ts):
# true synonyms / abbreviations only, never "related" technologies.
SKILL_ALIASES: dict[str, dict[str, Any]] = {
    "javascript": {"label": "JavaScript", "aliases": ["js", "javascript", "ecmascript", "es6"]},
    "typescript": {"label": "TypeScript", "aliases": ["ts", "typescript"]},
    "postgresql": {"label": "PostgreSQL", "aliases": ["postgres", "postgresql", "psql", "pgsql"]},
    "python": {"label": "Python", "aliases": ["python", "python3", "py"]},
    "nodejs": {"label": "Node.js", "aliases": ["node", "nodejs", "node.js"]},
    "react": {"label": "React", "aliases": ["react", "reactjs", "react.js"]},
    "vue": {"label": "Vue", "aliases": ["vue", "vuejs", "vue.js"]},
    "nextjs": {"label": "Next.js", "aliases": ["next", "nextjs", "next.js"]},
    "kubernetes": {"label": "Kubernetes", "aliases": ["kubernetes", "k8s"]},
    "golang": {"label": "Go", "aliases": ["go", "golang"]},
    "csharp": {"label": "C#", "aliases": ["c#", "csharp", "c sharp"]},
    "cpp": {"label": "C++", "aliases": ["c++", "cpp"]},
    "aws": {"label": "AWS", "aliases": ["aws", "amazon web services"]},
    "gcp": {"label": "GCP", "aliases": ["gcp", "google cloud", "google cloud platform"]},
    "azure": {"label": "Azure", "aliases": ["azure", "microsoft azure"]},
    "ml": {"label": "Machine Learning", "aliases": ["ml", "machine learning"]},
    "ai": {"label": "Artificial Intelligence", "aliases": ["ai", "artificial intelligence"]},
    "nlp": {"label": "NLP", "aliases": ["nlp", "natural language processing"]},
    "sql": {"label": "SQL", "aliases": ["sql"]},
    "mongodb": {"label": "MongoDB", "aliases": ["mongodb", "mongo"]},
    "docker": {"label": "Docker", "aliases": ["docker"]},
    "graphql": {"label": "GraphQL", "aliases": ["graphql", "gql"]},
    "cicd": {"label": "CI/CD", "aliases": ["ci/cd", "cicd", "ci cd"]},
    "html": {"label": "HTML", "aliases": ["html", "html5"]},
    "css": {"label": "CSS", "aliases": ["css", "css3"]},
    "tailwind": {"label": "Tailwind CSS", "aliases": ["tailwind", "tailwindcss", "tailwind css"]},
    "restapi": {"label": "REST APIs", "aliases": ["rest", "rest api", "rest apis", "restful", "restful api"]},
}
ALIASES: dict[str, str] = {a: cid for cid, v in SKILL_ALIASES.items() for a in v["aliases"]}  # alias -> canonical id

# Deterministic normalisation for descriptive JD requirement phrases. These are explicit
# phrase-to-skill mappings, not generic substring matching. AI semantic matching is only a
# later fallback for other evidence-grounded equivalences.
# Directional implication: a concrete relational DB engine can support a generic SQL requirement,
# but generic SQL never proves experience with a specific engine. An implied match is labelled
# and earns partial (75%) credit rather than being treated as exact equivalence.
IMPLIED_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "sql": ("postgresql", "mysql", "sqlite", "mariadb", "sql server", "microsoft sql server", "oracle database"),
    "sql database": ("postgresql", "mysql", "sqlite", "mariadb", "sql server", "microsoft sql server", "oracle database"),
    "sql databases": ("postgresql", "mysql", "sqlite", "mariadb", "sql server", "microsoft sql server", "oracle database"),
    "relational database": ("postgresql", "mysql", "sqlite", "mariadb", "sql server", "microsoft sql server", "oracle database"),
    "relational databases": ("postgresql", "mysql", "sqlite", "mariadb", "sql server", "microsoft sql server", "oracle database"),
    "sql and relational databases": ("postgresql", "mysql", "sqlite", "mariadb", "sql server", "microsoft sql server", "oracle database"),
}

LEARNING_GUIDES: dict[str, tuple[str, str]] = {
    "python": ("Build a small tested CLI or API endpoint in Python.", "2-4 hours"),
    "fastapi": ("Build a CRUD REST endpoint with validation and error handling.", "4-8 hours"),
    "rest api development": ("Implement and document one REST endpoint, including status codes.", "3-6 hours"),
    "sql": ("Practise SELECT, JOIN, GROUP BY, constraints and indexes on a small database.", "4-8 hours"),
    "sql and relational databases": ("Design a relational schema and practise joins, constraints and transactions.", "4-8 hours"),
    "git version control": ("Use a branch, commits, merge conflict resolution and a pull request in a small repo.", "2-4 hours"),
    "automated testing with pytest": ("Write unit tests plus one API integration test, including a failure case.", "2-5 hours"),
    "docker and containerisation": ("Containerise a small service with a Dockerfile and environment variables.", "4-8 hours"),
    "typescript or react fundamentals": ("Build a typed form and a small component that consumes an API.", "6-12 hours"),
    "redis caching": ("Add a TTL cache to a local API and test cache hits and misses.", "3-6 hours"),
    "ci/cd pipelines": ("Create a CI workflow that runs linting and automated tests on each push.", "3-6 hours"),
    "problem solving and data structures": ("Practise arrays, hash maps, stacks, queues and complexity analysis.", "6-12 hours"),
}

PHRASE_ALTERNATIVES: dict[str, tuple[str, ...]] = {
    "automated testing with pytest": ("pytest",),
    "fastapi or rest api development": ("fastapi", "rest api", "rest apis", "restful api"),
    "git version control": ("git",),
    "problem solving and data structures": ("data structures and algorithms", "data structures", "problem solving"),
    "python programming": ("python",),
    "sql and relational databases": ("sql",),
    "docker and containerisation": ("docker",),
    "docker and containerization": ("docker",),
    "typescript or react fundamentals": ("typescript", "react"),
    "ci/cd pipelines": ("ci/cd", "cicd", "continuous integration and continuous delivery"),
    "redis caching": ("redis",),
}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).lower().strip())


def canonical(s: str) -> str:
    c = clean(s)
    if not c:
        return ""
    return ALIASES.get(c) or ALIASES.get(c.replace(" ", "")) or c


def _dedupe(values: Any) -> list[str]:
    out: dict[str, str] = {}
    for x in values or []:
        t = re.sub(r"\s+", " ", str(x).strip())
        if t and len(t) <= MAX_SKILL_LENGTH and canonical(t) not in out:
            out[canonical(t)] = t
    return list(out.values())


def _fuzzy_similarity(a: str, b: str, key_a: str, key_b: str, cat_a: str | None, cat_b: str | None) -> float | None:
    """Similarity (0-1) if the guarded fuzzy rule accepts the pair, else None."""
    if min(len(a), len(b)) < FUZZY_MIN_LENGTH or a[0] != b[0]:
        return None
    if re.findall(r"\d+", a) != re.findall(r"\d+", b):
        return None
    if key_a in SKILL_ALIASES and key_b in SKILL_ALIASES and key_a != key_b:
        return None  # two known, different skills
    if cat_a in _RADIX_CODES and cat_b in _RADIX_CODES and cat_a != cat_b:
        return None  # category guard
    ratio = SequenceMatcher(None, a, b).ratio()
    return round(ratio, 3) if ratio >= FUZZY_THRESHOLD else None


def _candidate_pool(candidate_skills: list[Any]) -> list[dict[str, Any]]:
    pool: dict[str, dict[str, Any]] = {}
    for item in candidate_skills or []:
        name, cat = (item.get("skill_name"), item.get("category_code")) if isinstance(item, dict) else (item, None)
        if not name or not str(name).strip():
            continue
        key = canonical(str(name))
        pool.setdefault(key, {"name": str(name).strip(), "clean": clean(str(name)), "key": key, "category": cat,
                              "evidence": str(item.get("evidence") or "") if isinstance(item, dict) else "",
                              "confidence": str(item.get("confidence") or "low") if isinstance(item, dict) else "low"})
    return list(pool.values())


def _find(skill: str, category: str | None, pool: list[dict[str, Any]], fuzzy: bool) -> dict[str, Any] | None:
    c, k = clean(skill), canonical(skill)
    for p in pool:
        if p["clean"] == c:
            return {"match_type": "exact", "matched_with": p["name"], "similarity": 1.0, "evidence": p.get("evidence", ""), "confidence": p.get("confidence", "low")}
    for p in pool:
        if p["key"] == k:
            return {"match_type": "alias", "matched_with": p["name"], "similarity": 1.0, "evidence": p.get("evidence", ""), "confidence": p.get("confidence", "low")}
    phrase_key = re.sub(r"\s+", " ", c.replace("&", "and")).strip()
    for alternative in PHRASE_ALTERNATIVES.get(phrase_key, ()):
        alt_clean = clean(alternative)
        alt_key = canonical(alternative)
        for p in pool:
            if p["clean"] == alt_clean or p["key"] == alt_key:
                return {"match_type": "phrase", "matched_with": p["name"], "similarity": 1.0, "evidence": p.get("evidence", ""), "confidence": p.get("confidence", "low")}
    implied_targets = IMPLIED_REQUIREMENTS.get(phrase_key, ())
    if implied_targets and (category is None or category == "SQL"):
        target_keys = {canonical(x) for x in implied_targets}
        for p in pool:
            if p["key"] in target_keys and p.get("category") in (None, "", "SQL"):
                return {"match_type": "implied", "matched_with": p["name"], "similarity": 0.75,
                        "evidence": p.get("evidence", ""), "confidence": p.get("confidence", "low")}
    if fuzzy:
        best = None
        for p in pool:
            sim = _fuzzy_similarity(c, p["clean"], k, p["key"], category, p["category"])
            if sim is not None and (best is None or sim > best[0]):
                best = (sim, p)
        if best:
            return {"match_type": "fuzzy", "matched_with": best[1]["name"], "similarity": best[0], "evidence": best[1].get("evidence", ""), "confidence": best[1].get("confidence", "low")}
    return None


def compute_skill_match(candidate_skills: list[Any], job: dict[str, Any], *, fuzzy: bool = True,
                        semantic_matches: dict[str, str] | None = None) -> dict[str, Any]:
    """``candidate_skills``: names or skill dicts. ``job``: required_skills / preferred_skills (+ optional ``skills`` dicts for categories).

    ``semantic_matches`` is an optional, pre-validated mapping from canonical JD skill labels to
    exact candidate skill labels. The deterministic scorer re-validates these labels against the
    candidate pool and category constraints before awarding credit.
    """
    pool = _candidate_pool(candidate_skills)
    categories = {canonical(s.get("skill_name", "")): s.get("category_code") for s in (job.get("skills") or []) if isinstance(s, dict)}
    required = _dedupe(job.get("required_skills"))
    required_keys = {canonical(x) for x in required}
    preferred = [s for s in _dedupe(job.get("preferred_skills")) if canonical(s) not in required_keys]  # in both lists => counts once, as required
    possible = REQUIRED_WEIGHT * len(required) + PREFERRED_WEIGHT * len(preferred)

    details: list[dict[str, Any]] = []
    semantic_matches = semantic_matches or {}
    for rtype, names, weight in (("required", required, REQUIRED_WEIGHT), ("preferred", preferred, PREFERRED_WEIGHT)):
        for s in names:
            jd_category = categories.get(canonical(s))
            hit = _find(s, jd_category, pool, fuzzy)
            if hit is None:
                # Semantic suggestions only count if the target skill exists in the submitted profile.
                candidate_label = semantic_matches.get(canonical(s))
                if candidate_label:
                    target_key = canonical(candidate_label)
                    candidate_hit = next((p for p in pool if p["key"] == target_key or p["clean"] == clean(candidate_label)), None)
                    if candidate_hit is not None:
                        candidate_category = candidate_hit.get("category")
                        if not (jd_category in _RADIX_CODES and candidate_category in _RADIX_CODES and jd_category != candidate_category):
                            hit = {"match_type": "semantic_ai", "matched_with": candidate_hit["name"], "similarity": 0.9,
                                   "evidence": candidate_hit.get("evidence", ""), "confidence": candidate_hit.get("confidence", "low")}
            factor = 0.75 if hit and hit["match_type"] == "implied" else (0.9 if hit and hit["match_type"] == "semantic_ai" else 1.0)
            earned_points = round(weight * factor, 2) if hit else 0
            d = {"skill": s, "requirement_type": rtype, "weight": weight, "matched": hit is not None,
                 "match_type": hit["match_type"] if hit else None, "matched_with": hit["matched_with"] if hit else None,
                 "similarity": hit["similarity"] if hit else None,
                 "evidence_quote": hit.get("evidence", "") if hit else None,
                 "evidence_confidence": hit.get("confidence", "low") if hit else None,
                 "score_factor": factor if hit else 0,
                 "points_earned": earned_points, "points_lost": round(weight - earned_points, 2) if hit else weight}
            details.append(d)

    earned = sum(d["points_earned"] for d in details)
    exact_earned = sum(d["points_earned"] for d in details if d["match_type"] in ("exact", "alias", "phrase"))
    pct = lambda n: round(n / possible * 100, 2) if possible else None
    score = pct(earned)
    mr = [d["skill"] for d in details if d["matched"] and d["requirement_type"] == "required"]
    xr = [d["skill"] for d in details if not d["matched"] and d["requirement_type"] == "required"]
    mp = [d["skill"] for d in details if d["matched"] and d["requirement_type"] == "preferred"]
    xp = [d["skill"] for d in details if not d["matched"] and d["requirement_type"] == "preferred"]

    gaps = []
    for d in details:
        if d["matched"]:
            continue
        share = round(d["weight"] / possible * 100, 2)
        req = d["requirement_type"] == "required"
        why = (f"{d['skill']} is a required skill worth {d['weight']} of {possible} points ({share}% of the score); "
               f"it is the biggest lever on this match." if req else
               f"{d['skill']} is a preferred skill worth {d['weight']} of {possible} points ({share}% of the score); "
               f"missing it costs less than a missing required skill.")
        guide = LEARNING_GUIDES.get(canonical(d["skill"]))
        if guide is None:
            guide = (f"Study the core concepts of {d['skill']} and add a small project that demonstrates them.", "2-6 hours (rough estimate)")
        gaps.append({"priority": "high" if req else "medium", "skill": d["skill"], "category": d["requirement_type"],
                     "points_lost": d["points_lost"], "score_impact_percent": share, "why": why,
                     "learn_next": {"action": guide[0], "estimated_effort": guide[1], "estimate_note": "Planning estimate, not measured study time."},
                     "message": (f"Build and demonstrate {d['skill']}; it is required for this role." if req
                                 else f"Consider gaining {d['skill']}; it is preferred for this role.")})
    fuzzy_hits = [d for d in details if d["match_type"] == "fuzzy"]
    return {
        "status": "scored" if score is not None else "unable_to_calculate", "match_score": score,
        "score_label": f"{score:.2f}%" if score is not None else "Unable to calculate",
        "reason": None if score is not None else "No required or preferred skills were provided.",
        "weights": {"required_weight": REQUIRED_WEIGHT, "preferred_weight": PREFERRED_WEIGHT},
        "points": {"earned": earned, "possible": possible},
        "matched_skills": mr + mp, "missing_skills": xr + xp,
        "matched_required_skills": mr, "missing_required_skills": xr,
        "matched_preferred_skills": mp, "missing_preferred_skills": xp,
        "counts": {"matched_required": len(mr), "missing_required": len(xr), "matched_preferred": len(mp), "missing_preferred": len(xp)},
        "match_details": details, "gaps": gaps, "recommendations": gaps,
        "exact_only_score": pct(exact_earned), "fuzzy_matches": [{"skill": d["skill"], "matched_with": d["matched_with"], "similarity": d["similarity"]} for d in fuzzy_hits],
        "methodology": (f"Each JD skill is matched by exact text, explicit alias, small explicit descriptive-phrase map, guarded fuzzy spelling (>= {FUZZY_THRESHOLD}), "
                        f"then optional evidence-grounded AI semantic equivalence. Score = points earned / points possible; "
                        f"required = {REQUIRED_WEIGHT}, preferred = {PREFERRED_WEIGHT}. A skill in both lists counts once, as required. "
                        f"exact_only_score includes exact/alias/explicit phrase matches and excludes fuzzy, implied and semantic suggestions. "
                        "Directional implied matches earn 75% credit; accepted semantic AI matches earn 90% credit."),
        "disclaimer": "Skill-coverage estimate only; not a prediction of hiring success.",
    }
