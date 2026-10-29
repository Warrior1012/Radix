from typing import Literal
from pydantic import BaseModel, Field, field_validator

from .contract import SKILL_CATEGORY_CODES as CATEGORY_CODES
CONFIDENCE_VALUES = {"high", "medium", "low"}

class Skill(BaseModel):
    skill_name: str = Field(min_length=1, max_length=120)
    category_code: str
    evidence: str = Field(min_length=1, max_length=500)
    confidence: Literal["high", "medium", "low"]
    # Extension field (not in the 4-field brief object). None = model did not say; resolved later in requirement_type.py.
    requirement_type: Literal["required", "preferred"] | None = None

    @field_validator("requirement_type", mode="before")
    @classmethod
    def normalize_requirement_type(cls, value):
        if isinstance(value, str) and value.strip().lower() in ("required", "preferred"):
            return value.strip().lower()
        return None

    @field_validator("category_code")
    @classmethod
    def valid_category(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in CATEGORY_CODES:
            raise ValueError(f"Unsupported category_code: {value}")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value

class JDResult(BaseModel):
    source_type: Literal["jd"] = "jd"
    source_file: str
    company: str | None = None
    role: str | None = None
    skills: list[Skill] = Field(min_length=1, max_length=100)
    extraction_method: str = "llm"
    id: str | None = None
    created_at: str | None = None
