"""Clean and analyze job descriptions for the Job Extraction MVP."""

from __future__ import annotations

import re

from app.services.job_parser import SKILL_TAXONOMY


REMOVE_HEADINGS = (
    "about us",
    "about the company",
    "company information",
    "who we are",
    "benefits",
    "perks",
    "compensation",
    "equal employment opportunity",
    "equal opportunity",
    "privacy notice",
    "privacy notices",
    "applicant privacy",
    "ai hiring disclaimer",
    "ai hiring disclaimers",
    "legal",
    "legal language",
)

PRIORITY_HEADINGS = (
    "responsibilities",
    "what you will do",
    "what you'll do",
    "duties",
    "qualifications",
    "minimum qualifications",
    "basic qualifications",
    "requirements",
    "preferred qualifications",
    "preferred skills",
    "technical skills",
    "skills",
)

NOISE_PHRASES = (
    "equal opportunity",
    "eeo",
    "paid sick",
    "health insurance",
    "dental insurance",
    "vision insurance",
    "401(k)",
    "401k",
    "reasonable accommodation",
    "protected veteran",
    "privacy notice",
    "personal information",
    "background check",
    "ai tools",
    "automated decision",
    "local law",
    "federal law",
)


def clean_job_description(text: str) -> str:
    sections = split_job_sections(text)
    priority_content = [
        content
        for heading, content in sections.items()
        if _matches_heading(heading, PRIORITY_HEADINGS) and not _matches_heading(heading, REMOVE_HEADINGS)
    ]
    chunks = priority_content if priority_content else list(sections.values())
    paragraphs = []

    for chunk in chunks:
        for paragraph in _paragraphs(chunk):
            if not _is_noise(paragraph):
                paragraphs.append(paragraph)

    return re.sub(r"\s+", " ", "\n".join(paragraphs)).strip()


def extract_responsibilities(cleaned_description: str) -> list[str]:
    return _extract_items_by_heading(cleaned_description, ("responsibilities", "what you will do", "duties"))


def extract_qualifications(cleaned_description: str) -> list[str]:
    return _extract_items_by_heading(
        cleaned_description,
        ("qualifications", "requirements", "preferred skills", "technical skills", "skills"),
    )


def extract_technical_skills(cleaned_description: str) -> list[str]:
    lowered = cleaned_description.lower()
    skills = []
    for terms in SKILL_TAXONOMY.values():
        for term in terms:
            pattern = rf"(?<![a-zA-Z0-9]){re.escape(term)}s?(?![a-zA-Z0-9])"
            if re.search(pattern, lowered):
                skills.append(term)
    return sorted(set(skills))


def split_job_sections(text: str) -> dict[str, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    sections: dict[str, list[str]] = {"job description": []}
    current = "job description"

    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        heading = _canonical_heading(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(raw_line)

    return {
        heading: "\n".join(lines).strip()
        for heading, lines in sections.items()
        if "\n".join(lines).strip()
    }


def _extract_items_by_heading(text: str, headings: tuple[str, ...]) -> list[str]:
    sections = split_job_sections(text)
    selected = [
        content
        for heading, content in sections.items()
        if _matches_heading(heading, headings)
    ]
    source = "\n".join(selected) if selected else text
    return _items(source)[:20]


def _items(text: str) -> list[str]:
    found = []
    for line in text.splitlines():
        cleaned = re.sub(r"^[\-*•\d.)\s]+", "", line).strip()
        if cleaned:
            found.append(cleaned)
    if found:
        return found
    return [sentence.strip() for sentence in re.split(r"(?<=\.)\s+", text) if sentence.strip()]


def _paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"(?:\n\s*){2,}|(?<=\.)\s+", text) if paragraph.strip()]


def _is_noise(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in NOISE_PHRASES)


def _canonical_heading(line: str) -> str:
    normalized = re.sub(r"[^a-zA-Z /'-]", "", line).strip().lower().rstrip(":")
    if len(normalized.split()) > 6:
        return ""
    if _matches_heading(normalized, REMOVE_HEADINGS + PRIORITY_HEADINGS):
        return normalized
    return ""


def _matches_heading(heading: str, choices: tuple[str, ...]) -> bool:
    normalized = heading.lower().strip().rstrip(":")
    return any(normalized == choice or choice in normalized for choice in choices)
