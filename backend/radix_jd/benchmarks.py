"""Official Role 4 three-company benchmark snapshot (local JSON). Joined by category_code only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contract import CATEGORIES, RADIX_CATEGORY_CODES

BENCHMARK_PATH = Path(__file__).resolve().parent.parent / "data" / "talent_check_company_skillsets.json"


def load_benchmarks(path: Path = BENCHMARK_PATH) -> list[dict[str, Any]]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))["companies"]
        normalized = []
        for row in rows:
            by_code = {str(k).upper(): int(v) for k, v in row["skill_levels"].items()}
            if set(by_code) != set(RADIX_CATEGORY_CODES) or any(not 1 <= v <= 10 for v in by_code.values()):
                raise ValueError("Each company must define all 12 RADIX categories with levels 1-10")
            normalized.append({
                **row,
                "levels_by_code": by_code,  # canonical: always look up by category_code
                # Deprecated positional view, kept only for backward compatibility; do NOT use for joins.
                "levels": [by_code[code] for code, _ in CATEGORIES],
            })
        if len(normalized) != 3:
            raise ValueError("Expected exactly three companies in the hackathon snapshot")
        return normalized
    except Exception as exc:
        raise RuntimeError(f"Invalid or missing Talent Check benchmark JSON at {path}: {type(exc).__name__}") from exc
