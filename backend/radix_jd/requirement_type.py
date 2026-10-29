"""Required vs preferred classification for JD skills (Role 1, defect D1).

Why this exists: the model's per-skill value can be wrong or absent, and the old code guessed from the
*evidence string only* (which rarely contains the section heading), so "Preferred Skills" items became "required".

Precedence (most specific wins), recorded in ``requirement_basis``:
  1. ``inline_marker``    - the item's own sentence says preferred / nice to have / "is a plus" / ...
  2. ``section_heading``  - nearest preceding heading such as "Preferred Skills" / "Required Skills"
  3. ``model``            - the LLM's own requirement_type, if valid
  4. ``default``          - ``required`` (documented default for ambiguous wording; never silently "preferred")
"""
from __future__ import annotations

import re

REQUIREMENT_TYPES = ("required", "preferred")

_PREFERRED = (
    r"preferred|nice[- ]to[- ]haves?|good[- ]to[- ]haves?|bonus|desirable|desired|optional|advantageous|"
    r"an? advantage|added advantage|a plus|plus points?|would be (?:a )?(?:plus|bonus|nice|great|beneficial)"
)
_REQUIRED_HEAD = r"required|requirements?|must[- ]haves?|minimum|mandatory|essential|basic qualifications|key skills|qualifications"
_SECTION_BREAK = (
    r"responsibilit|what you.?ll (?:do|work)|about (?:us|the (?:role|company|team))|benefits|we offer|perks|"
    r"how to apply|company overview|role overview|job (?:description|summary|overview)|who we are|compensation"
)
_PREFERRED_RE = re.compile(r"\b(?:%s)\b" % _PREFERRED, re.I)
_REQUIRED_HEAD_RE = re.compile(r"\b(?:%s)\b" % _REQUIRED_HEAD, re.I)
_BREAK_RE = re.compile(_SECTION_BREAK, re.I)
_BULLET_RE = re.compile(r"^\s*(?:[-•*·●▪‣◦►]|\d+[.)])\s*")


def _locate_all(evidence: str, text: str, cap: int = 20) -> list[int]:
    """Character indexes of every occurrence of the evidence, tolerant of whitespace/line-break differences."""
    words = evidence.strip().strip("\"'“”").split()
    if not words:
        return []
    pattern = r"\s+".join(re.escape(w) for w in words)
    return [m.start() for m in re.finditer(pattern, text, re.I)][:cap]


def _sentence_around(line: str, offset: int) -> str:
    """The sentence/clause of ``line`` containing ``offset`` (offset relative to the line)."""
    start = 0
    for m in re.finditer(r"(?<=[.!?;])\s+", line):
        if m.end() <= offset:
            start = m.end()
        else:
            return line[start:m.start()]
    return line[start:]


def _heading_kind(line: str) -> str | None:
    """'preferred' | 'required' | 'break' if the line is a section heading of that kind, else None."""
    s = line.strip()
    if not s or _BULLET_RE.match(s):
        return None
    words = s.rstrip(":").split()
    heading_ish = (s.endswith(":") and len(words) <= 10) or (len(words) <= 6 and not s.endswith((".", ",", ";")))
    if not heading_ish:
        return None
    if _PREFERRED_RE.search(s):
        return "preferred"
    if _REQUIRED_HEAD_RE.search(s):
        return "required"
    if _BREAK_RE.search(s):
        return "break"
    return None


def _classify_at(pos: int, text: str) -> tuple[str | None, str | None]:
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    line_end = len(text) if line_end < 0 else line_end
    line = text[line_start:line_end]

    # 1. inline marker in the item's own sentence
    sentence = _sentence_around(line, pos - line_start)
    inline_head = re.match(r"\s*([^:]{2,40}):", sentence)
    body = sentence[inline_head.end():] if inline_head else sentence
    if _PREFERRED_RE.search(body):
        return "preferred", "inline_marker"

    # 2a. "Preferred Skills: A, B, C" (heading and items on the same line)
    if inline_head:
        head = inline_head.group(1)
        if _PREFERRED_RE.search(head):
            return "preferred", "section_heading"
        if _REQUIRED_HEAD_RE.search(head):
            return "required", "section_heading"

    # 2b. nearest preceding heading line (bounded look-back)
    for prev in reversed(text[:line_start].splitlines()[-80:]):
        kind = _heading_kind(prev)
        if kind in ("preferred", "required"):
            return kind, "section_heading"
        if kind == "break":
            break
    return None, None


def classify_from_text(evidence: str, text: str) -> tuple[str | None, str | None]:
    """(type, basis) from the source text alone, or (None, None) if not determinable.

    If the evidence occurs several times with conflicting classifications (skill listed in both a required and a
    preferred section), the skill is 'required' - the stricter reading, matching the prompt rule.
    """
    results = [r for r in (_classify_at(p, text) for p in _locate_all(evidence, text)) if r[0]]
    if not results:
        return None, None
    kinds = {r[0] for r in results}
    if kinds == {"preferred"}:
        return results[0]
    if "required" in kinds:
        return next(r for r in results if r[0] == "required")
    return results[0]


def resolve_requirement_type(model_value: object, evidence: str, text: str) -> tuple[str, str]:
    """Final (requirement_type, requirement_basis) for one skill. Never raises."""
    from_text, basis = classify_from_text(evidence or "", text or "")
    if from_text:
        return from_text, basis or "section_heading"
    if isinstance(model_value, str) and model_value.strip().lower() in REQUIREMENT_TYPES:
        return model_value.strip().lower(), "model"
    return "required", "default"
