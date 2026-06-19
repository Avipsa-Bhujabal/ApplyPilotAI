"""Direct job URL extraction for public pages."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.services.jd_cleaner import clean_job_description


BLOCKED_DOMAINS = ("linkedin.com", "indeed.com", "glassdoor.com")


def extract_direct_url_jobs(company_name: str, url: str) -> list[dict[str, Any]]:
    _validate_direct_url(url)

    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "ApplyPilotAI/1.0"},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    raw_description = _extract_description_text(soup)
    title = _extract_title(soup)
    location = _meta_content(soup, "jobLocation") or _find_labeled_text(soup, "location")
    employment_type = _meta_content(soup, "employmentType") or _find_labeled_text(soup, "employment")

    return [
        {
            "title": title,
            "company": company_name,
            "location": location,
            "department": _find_labeled_text(soup, "department"),
            "employment_type": employment_type,
            "apply_url": url,
            "raw_description": raw_description,
            "cleaned_description": clean_job_description(raw_description),
            "source_type": "Direct URL",
            "source_url": url,
        }
    ]


def _validate_direct_url(url: str) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a valid public http or https URL.")
    if any(domain in parsed.netloc.lower() for domain in BLOCKED_DOMAINS):
        raise ValueError("LinkedIn, Indeed, and Glassdoor scraping is intentionally disabled.")


def _extract_title(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    if heading:
        return heading.get_text(" ", strip=True)
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return "Untitled Job"


def _extract_description_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return main.get_text("\n", strip=True)


def _meta_content(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find(attrs={"property": name}) or soup.find(attrs={"name": name})
    return tag.get("content", "").strip() if tag else ""


def _find_labeled_text(soup: BeautifulSoup, label: str) -> str:
    pattern = label.lower()
    for text in soup.stripped_strings:
        lowered = text.lower()
        if pattern in lowered and ":" in text:
            return text.split(":", 1)[1].strip()
    return ""
