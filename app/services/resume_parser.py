"""Resume parsing helpers.

The MVP intentionally extracts only facts already present in the pasted resume.
It does not infer employment history, credentials, or accomplishments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


SECTION_ALIASES = {
    "skills": ("skills", "technical skills", "core skills", "competencies"),
    "experience": ("experience", "work experience", "professional experience", "employment"),
    "projects": ("projects", "selected projects"),
    "education": ("education", "academic background"),
    "certifications": ("certifications", "certificates", "licenses"),
}

STRUCTURED_SECTION_KEYS = (
    "skills",
    "experience",
    "projects",
    "education",
    "certifications",
)


@dataclass(frozen=True)
class ParsedResume:
    raw_text: str
    name: str
    email: str
    phone: str
    sections: dict[str, str]
    structured: dict[str, list[str]]


def normalize_whitespace(text: str) -> str:
    """Collapse noisy whitespace while preserving paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_resume(text: str) -> ParsedResume:
    cleaned = normalize_whitespace(text)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

    email = _first_match(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", cleaned)
    phone = _first_match(
        r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}",
        cleaned,
    )
    name = _guess_name(lines, email, phone)
    structured = _extract_structured_sections(lines)
    sections = {key: "\n".join(value).strip() for key, value in structured.items()}

    return ParsedResume(
        raw_text=cleaned,
        name=name,
        email=email,
        phone=phone,
        sections=sections,
        structured=structured,
    )


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return match.group(0).strip() if match else ""


def _guess_name(lines: list[str], email: str, phone: str) -> str:
    for line in lines[:8]:
        if email and email in line:
            continue
        if phone and phone in line:
            continue
        if len(line.split()) <= 5 and not re.search(r"[:@]|\d", line):
            return line
    return ""


def _canonical_heading(line: str) -> str | None:
    candidate = re.sub(r"[^a-zA-Z ]", "", line).strip().lower()
    for canonical, aliases in SECTION_ALIASES.items():
        if candidate in aliases:
            return canonical
    return None


def _extract_structured_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {key: [] for key in STRUCTURED_SECTION_KEYS}
    current: str | None = None

    for line in lines:
        heading = _canonical_heading(line)
        if heading:
            current = heading
            continue
        if current:
            sections[current].extend(_split_section_line(line))

    return {key: _clean_items(value) for key, value in sections.items()}


def _split_section_line(line: str) -> list[str]:
    if "," in line and len(line) < 160:
        return [part.strip() for part in line.split(",")]
    return [line.strip()]


def _clean_items(items: list[str]) -> list[str]:
    cleaned = []
    for item in items:
        normalized = re.sub(r"^[\-*•\d.)\s]+", "", item).strip()
        if normalized:
            cleaned.append(normalized)
    return cleaned
