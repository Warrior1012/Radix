"""Role 3 Profile Builder backend: durable storage, user-edit tracking, and merge-not-overwrite for re-parsed resumes.

Storage decision (D4c): the source of truth is ALWAYS a durable store, never an in-process dict.
* Supabase configured  -> ``radix_candidate_profiles`` (failures are surfaced as errors, never masked).
* Supabase NOT configured -> local JSON files in ``PROFILE_STORE_DIR`` (default ``backend/data/profiles``),
  written atomically. Profiles therefore survive a backend restart in local/demo mode too.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contract import (CANDIDATE_ID_RE, PROFILE_LIST_FIELDS, PROFILE_SCALAR_FIELDS, Profile, ProfileSkill)

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "profiles"


class InvalidCandidateId(ValueError):
    pass


def check_candidate_id(candidate_id: str) -> str:
    if not isinstance(candidate_id, str) or not CANDIDATE_ID_RE.match(candidate_id):
        raise InvalidCandidateId("Invalid candidate id.")
    return candidate_id


class FileProfileStore:
    """One JSON file per candidate. The id is validated against a strict pattern, so it can never escape the directory."""

    def __init__(self, directory: Path | str | None = None):
        self._dir = Path(directory) if directory else None

    @property
    def directory(self) -> Path:
        return self._dir or Path(os.getenv("PROFILE_STORE_DIR", "") or DEFAULT_DIR)

    def _path(self, candidate_id: str) -> Path:
        return self.directory / f"{check_candidate_id(candidate_id)}.json"

    def save(self, item: dict[str, Any]) -> None:
        path = self._path(item["candidate_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(item, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)  # atomic: a crash never leaves a half-written profile
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, candidate_id: str) -> dict[str, Any] | None:
        path = self._path(candidate_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None

    def list(self) -> list[dict[str, Any]]:
        if not self.directory.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in self.directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("candidate_id"):
                    rows.append(data)
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda row: str(row.get("saved_at") or ""), reverse=True)

    def delete(self, candidate_id: str) -> bool:
        path = self._path(candidate_id)
        if not path.exists():
            return False
        path.unlink()
        return True


class ProfileRepository:
    """Routes to Supabase when configured, else to the local file store. Holds NO cache (nothing can mask the store)."""

    def __init__(self, supabase: Any, files: FileProfileStore | None = None):
        self.supabase = supabase
        self.files = files or FileProfileStore()

    @property
    def mode(self) -> str:
        return "supabase" if self.supabase.configured else "local-file"

    def save(self, item: dict[str, Any]) -> None:
        check_candidate_id(item["candidate_id"])
        (self.supabase.upsert_profile if self.supabase.configured else self.files.save)(item)

    def get(self, candidate_id: str) -> dict[str, Any] | None:
        check_candidate_id(candidate_id)
        return self.supabase.get_profile(candidate_id) if self.supabase.configured else self.files.get(candidate_id)

    def list(self) -> list[dict[str, Any]]:
        return self.supabase.list_profiles() if self.supabase.configured else self.files.list()

    def delete(self, candidate_id: str) -> bool:
        check_candidate_id(candidate_id)
        return self.supabase.delete_profile(candidate_id) if self.supabase.configured else self.files.delete(candidate_id)


# --------------------------------------------------------------------------- validation on save
def validate_for_save(profile: Profile) -> list[dict[str, str]]:
    """Rules from the original Role 3 UI (zod): name required. Email is optional here but must be valid if present
    (the model already rejects malformed emails)."""
    errors = []
    if not profile.name.strip():
        errors.append({"field": "name", "message": "Name is required"})
    return errors


# --------------------------------------------------------------------------- edit tracking
def _skey(skill: dict[str, Any]) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", str(skill.get("skill_name", "")).lower()).strip() + "|" + str(skill.get("category_code", "OTHER")).upper()


def detect_user_edits(previous: dict[str, Any] | None, item: dict[str, Any]) -> dict[str, Any]:
    """Compare an incoming save with the stored version. Returns updated provenance (user_edited / dismissed).

    * A scalar field that changed since the last save is ``user_edited`` (re-parsing will not overwrite it).
    * A list item / skill that existed before and was removed is ``dismissed`` (re-parsing will not re-add it).
    """
    edited = set(item.get("user_edited") or []) | set((previous or {}).get("user_edited") or [])
    dismissed: dict[str, list[str]] = {k: list(v) for k, v in ((previous or {}).get("dismissed") or {}).items()}
    for k, v in (item.get("dismissed") or {}).items():
        dismissed[k] = list(dict.fromkeys([*dismissed.get(k, []), *v]))
    if previous:
        for f in PROFILE_SCALAR_FIELDS:
            if (previous.get(f) or "") != (item.get(f) or ""):
                edited.add(f)
        for f in PROFILE_LIST_FIELDS:
            now = {x.lower() for x in item.get(f, [])}
            gone = [x for x in previous.get(f, []) if x.lower() not in now]
            if gone:
                dismissed[f] = list(dict.fromkeys([*dismissed.get(f, []), *[g.lower() for g in gone]]))
        now_keys = {_skey(s) for s in item.get("skills", [])}
        gone_sk = [_skey(s) for s in previous.get("skills", []) if _skey(s) not in now_keys]
        if gone_sk:
            dismissed["skills"] = list(dict.fromkeys([*dismissed.get("skills", []), *gone_sk]))
    # A re-added item is no longer dismissed.
    for f in PROFILE_LIST_FIELDS:
        have = {x.lower() for x in item.get(f, [])}
        if f in dismissed:
            dismissed[f] = [d for d in dismissed[f] if d not in have]
    if "skills" in dismissed:
        have_sk = {_skey(s) for s in item.get("skills", [])}
        dismissed["skills"] = [d for d in dismissed["skills"] if d not in have_sk]
    return {"user_edited": sorted(edited), "dismissed": {k: v for k, v in dismissed.items() if v}}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- merge (D4b)
def merge_resume_into_profile(current: dict[str, Any] | None, parsed: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Merge a freshly parsed resume profile into the person's current profile WITHOUT destroying their edits.

    Rules (all covered by tests):
    * scalar fields (name, email, education, cv_file): kept when the person edited them (``user_edited``) or the parsed
      value is empty; otherwise filled from the resume. Provenance goes to ``field_sources``.
    * list fields: union (current items first), de-duplicated case-insensitively; items the person dismissed are not re-added.
    * skills: matched by (name, category). A skill the person added by hand, or already gave a ``level``, is kept as is.
      A resume-sourced skill gets its evidence refreshed but keeps any level. New skills are appended with ``source: resume``.
      Skills are never deleted by a merge.
    """
    cur = Profile.model_validate(current or {}).model_dump()
    edited = set(cur["user_edited"])
    sources = dict(cur["field_sources"])
    report: dict[str, Any] = {"kept_user_fields": [], "updated_fields": [], "added": {}, "skills_added": 0,
                              "skills_refreshed": 0, "skills_kept_manual": 0, "skipped_dismissed": 0}
    merged = dict(cur)

    for f in PROFILE_SCALAR_FIELDS:
        new = str(parsed.get(f) or "").strip()
        old = str(cur.get(f) or "").strip()
        if old and (f in edited or sources.get(f) == "user"):
            if new and new != old:
                report["kept_user_fields"].append(f)
            continue
        if new and new != old:
            merged[f] = new
            sources[f] = "resume"
            report["updated_fields"].append(f)
        elif old and f not in sources:
            sources[f] = "user"

    dismissed = {k: set(v) for k, v in cur["dismissed"].items()}
    for f in PROFILE_LIST_FIELDS:
        items = list(cur[f])
        have = {x.lower() for x in items}
        added = 0
        for x in parsed.get(f) or []:
            if not isinstance(x, str):
                continue
            x = " ".join(x.split())
            if not x or x.lower() in have:
                continue
            if x.lower() in dismissed.get(f, set()):
                report["skipped_dismissed"] += 1
                continue
            items.append(x)
            have.add(x.lower())
            added += 1
        merged[f] = items
        if added:
            report["added"][f] = added

    by_key = {_skey(s): i for i, s in enumerate(cur["skills"])}
    skills = [dict(s) for s in cur["skills"]]
    for raw in parsed.get("skills") or []:
        try:
            new_skill = ProfileSkill.model_validate({k: v for k, v in raw.items() if k != "level"}).model_dump()
        except Exception:
            continue  # an invalid parsed skill never blocks the merge
        key = _skey(new_skill)
        if key in dismissed.get("skills", set()):
            report["skipped_dismissed"] += 1
            continue
        if key in by_key:
            existing = skills[by_key[key]]
            resume_sourced = existing.get("source") == "resume" or (existing.get("source") != "manual" and bool(existing.get("evidence_basis")))
            if not resume_sourced:  # added by hand: the person owns it entirely
                report["skills_kept_manual"] += 1
                continue
            for k in ("evidence", "confidence", "evidence_basis"):
                if k in new_skill and new_skill[k]:
                    existing[k] = new_skill[k]
            report["skills_refreshed"] += 1  # ``level`` (if the person set one) is untouched
        else:
            new_skill["source"] = "resume"
            new_skill["level"] = None
            skills.append(new_skill)
            by_key[key] = len(skills) - 1
            report["skills_added"] += 1
    merged["skills"] = skills
    merged["field_sources"] = sources
    result = Profile.model_validate(merged).model_dump()
    return result, report
