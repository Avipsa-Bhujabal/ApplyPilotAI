"""Configured job source loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_CONFIG_PATH = PROJECT_ROOT / "data" / "job_sources.json"


def load_job_sources(path: Path = SOURCE_CONFIG_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("data/job_sources.json must contain a list of source objects.")

    sources = []
    for item in data:
        if not isinstance(item, dict):
            continue
        source = _normalize_source(item)
        if source:
            sources.append(source)
    return sources


def _normalize_source(item: dict[str, Any]) -> dict[str, str]:
    company = str(item.get("company", "")).strip()
    url = str(item.get("url", "")).strip()
    source_type = str(item.get("source_type", "Auto-detect")).strip() or "Auto-detect"

    if not company or not url:
        return {}

    return {
        "company": company,
        "url": url,
        "source_type": source_type,
    }
