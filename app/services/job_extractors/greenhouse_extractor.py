"""Greenhouse job board extraction."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

from app.services.jd_cleaner import clean_job_description


GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def extract_greenhouse_jobs(company_name: str, url: str) -> list[dict[str, Any]]:
    token = _extract_board_token(url)
    if not token:
        raise ValueError("Could not find a Greenhouse board token in that URL.")

    response = requests.get(
        GREENHOUSE_API.format(token=token),
        params={"content": "true"},
        timeout=20,
        headers={"User-Agent": "ApplyPilotAI/1.0"},
    )
    response.raise_for_status()
    payload = response.json()

    jobs = []
    for job in payload.get("jobs", []):
        raw_description = _html_to_text(job.get("content") or "")
        jobs.append(
            {
                "title": job.get("title") or "",
                "company": company_name,
                "location": _location_name(job),
                "department": _department_name(job),
                "employment_type": "",
                "apply_url": job.get("absolute_url") or url,
                "raw_description": raw_description,
                "cleaned_description": clean_job_description(raw_description),
                "source_type": "Greenhouse",
                "source_url": url,
            }
        )
    return jobs


def _extract_board_token(url: str) -> str:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if "greenhouse.io" not in host or not path_parts:
        return ""
    if host.startswith("job-boards.") or host.startswith("boards."):
        return path_parts[0]
    match = re.search(r"greenhouse\.io/([^/?#]+)", url)
    return match.group(1) if match else ""


def _location_name(job: dict[str, Any]) -> str:
    location = job.get("location") or {}
    return location.get("name") or ""


def _department_name(job: dict[str, Any]) -> str:
    departments = job.get("departments") or []
    if not departments:
        return ""
    return departments[0].get("name") or ""


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)
