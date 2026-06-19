"""Lever job board extraction."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests

from app.services.jd_cleaner import clean_job_description


LEVER_API = "https://api.lever.co/v0/postings/{company}"


def extract_lever_jobs(company_name: str, url: str) -> list[dict[str, Any]]:
    company_token = _extract_company_token(url)
    if not company_token:
        raise ValueError("Could not find a Lever company token in that URL.")

    response = requests.get(
        LEVER_API.format(company=company_token),
        params={"mode": "json"},
        timeout=20,
        headers={"User-Agent": "ApplyPilotAI/1.0"},
    )
    response.raise_for_status()

    jobs = []
    for posting in response.json():
        categories = posting.get("categories") or {}
        raw_description = _lever_description(posting)
        jobs.append(
            {
                "title": posting.get("text") or "",
                "company": company_name,
                "location": categories.get("location") or "",
                "department": categories.get("team") or categories.get("department") or "",
                "employment_type": categories.get("commitment") or "",
                "apply_url": posting.get("hostedUrl") or posting.get("applyUrl") or url,
                "raw_description": raw_description,
                "cleaned_description": clean_job_description(raw_description),
                "source_type": "Lever",
                "source_url": url,
            }
        )
    return jobs


def _extract_company_token(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    if "lever.co" not in host or not path_parts:
        return ""
    return path_parts[0]


def _lever_description(posting: dict[str, Any]) -> str:
    parts = [
        posting.get("descriptionPlain") or "",
        posting.get("additionalPlain") or "",
    ]
    for list_item in posting.get("lists") or []:
        heading = list_item.get("text") or ""
        content = "\n".join(item.get("text") or "" for item in list_item.get("content") or [])
        parts.append(f"{heading}\n{content}".strip())
    return "\n\n".join(part for part in parts if part).strip()
