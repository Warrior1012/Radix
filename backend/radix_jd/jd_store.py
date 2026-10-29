"""Durable local store for analysed JDs so Role 5 can resolve a ``jd_id`` after a restart (D2b / D6c)."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

JD_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class InvalidJDId(ValueError):
    pass


def default_dir() -> Path:
    return Path(os.getenv("JD_STORE_DIR") or Path(__file__).resolve().parent.parent / "data" / "jds")


class FileJDStore:
    def __init__(self, directory: Path | None = None):
        self._dir = directory

    @property
    def directory(self) -> Path:
        return self._dir or default_dir()  # resolved lazily so tests can set JD_STORE_DIR

    def _path(self, jd_id: str) -> Path:
        if not isinstance(jd_id, str) or not JD_ID_RE.match(jd_id):
            raise InvalidJDId("Invalid jd_id.")
        return self.directory / f"{jd_id}.json"

    def save(self, jd: dict[str, Any]) -> None:
        path = self._path(str(jd.get("jd_id", "")))
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(jd, fh, ensure_ascii=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def get(self, jd_id: str) -> dict[str, Any] | None:
        path = self._path(jd_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def jd_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a ``jd_analytics_results`` row into the analysed-JD shape. Skills without a requirement_type are 'required'."""
    skills = [s for s in (row.get("skills") or []) if isinstance(s, dict) and s.get("skill_name")]
    req = [s["skill_name"] for s in skills if s.get("requirement_type", "required") != "preferred"]
    pref = [s["skill_name"] for s in skills if s.get("requirement_type") == "preferred"]
    return {"jd_id": str(row.get("id", "")), "source_type": "jd", "source_file": row.get("source_file"), "company": row.get("company"),
            "role": row.get("role"), "skills": skills, "required_skills": req, "preferred_skills": pref}
