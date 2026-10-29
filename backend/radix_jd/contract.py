"""RADIX shared data contract: the single place for category codes and cross-module shapes.

Rules (see docs/CONTRACT.md):
* Category joins are ALWAYS by ``category_code``. Never join benchmarks to skills by list position.
* ``OTHER`` is valid for a skill, but it is not one of the 12 benchmarked skillsets.
* Proficiency ``level`` is separate from extraction confidence. It is never inferred from a skill's mere presence.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Order follows the Role 4 ``skill_set_master`` IDs 1..12. Order is for DISPLAY only.
CATEGORIES: list[tuple[str, str]] = [
    ("COD", "Coding"),
    ("DSA", "Data Structures & Algorithms"),
    ("APTI", "Aptitude and Problem Solving"),
    ("COMM", "Communication Skills"),
    ("OOD", "Object-Oriented Programming and Design"),
    ("AI", "AI Native Engineering"),
    ("SQL", "SQL and Design"),
    ("SYSD", "System Design and Architecture"),
    ("CLOUD", "DevOps and Cloud"),
    ("SWE", "Software Engineering"),
    ("NETW", "Computer Networking"),
    ("OS", "Operating System"),
]

CATEGORY_LABELS: dict[str, str] = dict(CATEGORIES)
RADIX_CATEGORY_CODES: frozenset[str] = frozenset(CATEGORY_LABELS)  # the 12 benchmarked skillsets
SKILL_CATEGORY_CODES: frozenset[str] = RADIX_CATEGORY_CODES | {"OTHER"}  # allowed on a skill object
CONFIDENCE_VALUES = ("high", "medium", "low")
REQUIREMENT_TYPES = ("required", "preferred")

assert len(RADIX_CATEGORY_CODES) == 12


import re
from typing import Literal

from pydantic import field_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CANDIDATE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
PROFILE_LIST_FIELDS = ("hackathons", "internships", "experience", "certifications", "projects", "preferred_roles")
PROFILE_SCALAR_FIELDS = ("name", "email", "education", "cv_file")


class ProfileSkill(BaseModel):
    """One skill on a profile: the 4 contract fields + optional proficiency ``level``.

    ``level`` is 1-10 or ``None`` (= not assessed). Legacy ``0`` / ``""`` are normalised to ``None`` (never stored as 0).
    Extra extension fields (``evidence_basis``, ``source`` ...) are preserved.
    """

    model_config = ConfigDict(extra="allow")
    skill_name: str = Field(min_length=1, max_length=120)
    category_code: str = "OTHER"
    evidence: str = Field(default="", max_length=500)
    confidence: Literal["high", "medium", "low"] = "low"
    level: int | None = None

    @field_validator("skill_name", mode="before")
    @classmethod
    def _strip_name(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("category_code", mode="before")
    @classmethod
    def _category(cls, v: Any) -> str:
        v = "OTHER" if v in (None, "") else v
        if not isinstance(v, str) or v.strip().upper() not in SKILL_CATEGORY_CODES:
            raise ValueError(f"category_code must be one of {sorted(SKILL_CATEGORY_CODES)}")
        return v.strip().upper()

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, v: Any) -> Any:
        return "low" if v in (None, "") else (v.strip().lower() if isinstance(v, str) else v)

    @field_validator("evidence", mode="before")
    @classmethod
    def _evidence(cls, v: Any) -> Any:
        return "" if v is None else v

    @field_validator("level", mode="before")
    @classmethod
    def _level(cls, v: Any) -> int | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, bool):
            raise ValueError("level must be a number 1-10 or null")
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError("level must be a number 1-10 or null") from None
        if f != int(f):
            raise ValueError("level must be a whole number 1-10 or null")
        n = int(f)
        if n == 0:
            return None  # legacy "0 = unassessed"
        if not 1 <= n <= 10:
            raise ValueError("level must be between 1 and 10 (or null for not assessed)")
        return n


class Profile(BaseModel):
    """Candidate profile (Role 3 -> Roles 4 and 5). Skills are validated; unknown top-level keys are ignored."""

    candidate_id: str | None = None
    name: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=255)
    education: str = Field(default="", max_length=2000)
    skills: list[ProfileSkill] = Field(default_factory=list, max_length=200)
    hackathons: list[str] = Field(default_factory=list)
    internships: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    cv_file: str = ""
    role: str = Field(default="", max_length=100)  # target role (contract extension)
    # Provenance, maintained by the backend (see profiles.py). ``user_edited``: scalar fields a person changed.
    user_edited: list[str] = Field(default_factory=list)
    field_sources: dict[str, str] = Field(default_factory=dict)
    dismissed: dict[str, list[str]] = Field(default_factory=dict)  # items a person removed; re-parse must not re-add

    @field_validator("candidate_id")
    @classmethod
    def _cid(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if not CANDIDATE_ID_RE.match(v):
            raise ValueError("candidate_id may only contain letters, digits, '_' and '-' (max 64)")
        return v

    @field_validator("name", "education", "role", mode="before")
    @classmethod
    def _strip(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else ("" if v is None else v)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v: Any) -> Any:
        v = "" if v is None else v
        if isinstance(v, str):
            v = v.strip()
            if v and not _EMAIL_RE.match(v):
                raise ValueError("Enter a valid email")
        return v

    @field_validator("cv_file", mode="before")
    @classmethod
    def _cv(cls, v: Any) -> Any:
        v = "" if v is None else v
        if isinstance(v, str) and v.strip() and not v.strip().lower().endswith((".pdf", ".docx")):
            raise ValueError("CV must be a .pdf or .docx file")
        return v.strip() if isinstance(v, str) else v

    @field_validator(*PROFILE_LIST_FIELDS, mode="before")
    @classmethod
    def _lists(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("must be a list of strings")
        out: list[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("must be a list of strings")
            item = " ".join(item.split())
            if item and item.lower() not in {o.lower() for o in out}:
                out.append(item[:500])
        if len(out) > 50:
            raise ValueError("at most 50 entries")
        return out

    def skills_as_dicts(self) -> list[dict[str, Any]]:
        return [s.model_dump() for s in self.skills]


# --- Response contracts. ``extra='allow'`` so documented extension fields are preserved. ---
class GapEntry(BaseModel):
    model_config = ConfigDict(extra="allow")
    category_code: str
    required_level: int = Field(ge=1, le=10)
    candidate_level: int | None = Field(default=None, ge=1, le=10)  # None = unassessed (never 0)
    gap: bool | None = None  # None = unknown because the category is unassessed


class TalentCheckResult(BaseModel):
    """Official Role 4 output: company, skillset_gap, readiness_score."""

    model_config = ConfigDict(extra="allow")
    company: str
    readiness_score: float | None = Field(ge=0, le=100)  # None = nothing assessed yet
    skillset_gap: list[GapEntry] = Field(min_length=12, max_length=12)


class SkillMatchResult(BaseModel):
    """Official Role 5 output: jd_source_file, match_score, matched_skills, missing_skills."""

    model_config = ConfigDict(extra="allow")
    jd_source_file: str
    match_score: float | None = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
