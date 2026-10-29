"""Content-addressed cache for JD extraction responses.

Only the extracted JSON is stored, never the source JD text or provider credentials.
The key includes prompt version and target provider/model labels so material config
changes invalidate old entries. Keyword/demo fallbacks must never be cached as AI.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

CACHE_VERSION = "jd-extraction-v3"


def make_cache_key(text: str, targets: list[dict[str, Any]], prompt_version: str = CACHE_VERSION) -> str:
    normalised = " ".join((text or "").split())
    models = sorted(
        f"{t.get('provider', '')}:{t.get('model', '')}"
        for t in (targets or [])
    )
    material = json.dumps(
        {"version": prompt_version, "models": models, "text": normalised},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class JDExtractionCache:
    def __init__(self, path: Path | str | None = None):
        default = Path(__file__).resolve().parent.parent / "data" / "jd_extraction_cache.json"
        self.path = Path(path or os.getenv("JD_EXTRACTION_CACHE_PATH", str(default)))

    def _read(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._read().get(key)
        return dict(item) if isinstance(item, dict) else None

    def put(self, key: str, result: dict[str, Any]) -> None:
        meta = result.get("analysis_meta") if isinstance(result, dict) else {}
        processing_path = str((meta or {}).get("processing_path") or "")
        extraction_method = str(result.get("extraction_method") or "")
        if "keyword_fallback" in processing_path or "fallback" in extraction_method or extraction_method.startswith("demo"):
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        all_items = self._read()
        all_items[key] = result
        # Keep the cache bounded; entries are keyed by content/model configuration.
        if len(all_items) > 100:
            all_items = dict(list(all_items.items())[-100:])
        fd, temp_name = tempfile.mkstemp(prefix=".jd-cache-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(all_items, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
