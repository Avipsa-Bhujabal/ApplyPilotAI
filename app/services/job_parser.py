"""ATS-focused job description parsing.

The extractor is intentionally conservative: it only keeps terms that map to
recognized resume/ATS skill categories and ignores benefits, HR, legal, and EEO
language by design.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


CATEGORY_ORDER = (
    "Programming",
    "Cloud",
    "Data Engineering",
    "Databases",
    "Analytics",
    "Business",
)

SKILL_TAXONOMY: dict[str, tuple[str, ...]] = {
    "Programming": (
        ".net",
        "bash",
        "c#",
        "c++",
        "css",
        "django",
        "fastapi",
        "flask",
        "go",
        "graphql",
        "html",
        "java",
        "javascript",
        "kotlin",
        "laravel",
        "node.js",
        "php",
        "python",
        "r",
        "react",
        "rest api",
        "ruby",
        "rust",
        "scala",
        "spring",
        "typescript",
        "vue",
    ),
    "Cloud": (
        "aws",
        "azure",
        "cloudformation",
        "docker",
        "ec2",
        "gcp",
        "google cloud",
        "iam",
        "kubernetes",
        "lambda",
        "s3",
        "terraform",
    ),
    "Data Engineering": (
        "airflow",
        "apache beam",
        "apache spark",
        "databricks",
        "data lake",
        "data modeling",
        "data pipeline",
        "data warehouse",
        "dbt",
        "etl",
        "kafka",
        "pyspark",
        "snowflake",
    ),
    "Databases": (
        "bigquery",
        "dynamodb",
        "mongodb",
        "mysql",
        "nosql",
        "oracle",
        "postgresql",
        "redis",
        "sql",
        "sql server",
    ),
    "Analytics": (
        "a/b testing",
        "analytics",
        "business intelligence",
        "dashboard",
        "data analysis",
        "data visualization",
        "excel",
        "looker",
        "machine learning",
        "metrics",
        "power bi",
        "python pandas",
        "reporting",
        "tableau",
    ),
    "Business": (
        "agile",
        "business analysis",
        "change management",
        "communication",
        "crm",
        "cross-functional",
        "jira",
        "leadership",
        "product management",
        "project management",
        "requirements gathering",
        "salesforce",
        "scrum",
        "stakeholder management",
        "user stories",
    ),
}

CERTIFICATION_PATTERNS = (
    r"aws certified [a-z ]+",
    r"azure [a-z ]+ certification",
    r"certified scrum(?:master| master| product owner)",
    r"cissp",
    r"pmp",
    r"security\+",
)

CLEANER_REMOVE_HEADINGS = (
    "about us",
    "about the company",
    "company information",
    "who we are",
    "benefits",
    "perks",
    "compensation",
    "equal employment opportunity",
    "equal opportunity statement",
    "privacy notice",
    "privacy notices",
    "applicant privacy",
    "ai hiring disclaimer",
    "ai hiring disclaimers",
    "legal",
    "legal language",
)

CLEANER_PRIORITY_HEADINGS = (
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
    "experience",
)

IGNORED_LANGUAGE = (
    "benefits",
    "compensation",
    "equal employment opportunity",
    "equal opportunity",
    "eeo",
    "reasonable accommodation",
    "applicant privacy",
    "background check",
    "paid sick",
    "paid sick leave",
    "health insurance",
    "dental insurance",
    "vision insurance",
    "401k",
    "401(k)",
    "employee assistance",
    "company is an equal",
    "we are an equal",
    "protected veteran",
    "disability status",
    "local law",
    "federal law",
    "privacy notice",
    "privacy policy",
    "personal information",
    "artificial intelligence",
    "ai tools",
    "automated decision",
    "hiring process",
    "terms and conditions",
    "employment eligibility",
)


@dataclass(frozen=True)
class ParsedJob:
    raw_text: str
    cleaned_text: str
    raw_length: int
    cleaned_length: int
    keywords: list[str]
    keyword_counts: dict[str, int]
    categorized_keywords: dict[str, list[str]]


def parse_job_description(text: str, max_keywords: int = 60) -> ParsedJob:
    raw_text = text.strip()
    cleaned_text = clean_job_description(raw_text)
    categorized = extract_categorized_keywords(cleaned_text, max_keywords=max_keywords)
    keywords = [keyword for category in CATEGORY_ORDER for keyword in categorized[category]]
    counts = {keyword: _count_keyword(cleaned_text, keyword) for keyword in keywords}

    return ParsedJob(
        raw_text=re.sub(r"\s+", " ", raw_text).strip(),
        cleaned_text=cleaned_text,
        raw_length=len(raw_text),
        cleaned_length=len(cleaned_text),
        keywords=keywords,
        keyword_counts=counts,
        categorized_keywords=categorized,
    )


def clean_job_description(text: str) -> str:
    """Remove company/HR/legal noise and prioritize skill-bearing JD sections."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    sections = _split_sections(normalized)

    priority_chunks = [
        content
        for heading, content in sections
        if _heading_matches(heading, CLEANER_PRIORITY_HEADINGS)
        and not _heading_matches(heading, CLEANER_REMOVE_HEADINGS)
    ]
    source_chunks = priority_chunks if priority_chunks else [content for _, content in sections]

    cleaned_chunks = []
    for chunk in source_chunks:
        for paragraph in _split_paragraphs(chunk):
            if _is_noise_paragraph(paragraph):
                continue
            cleaned_chunks.append(paragraph)

    return re.sub(r"\s+", " ", "\n".join(cleaned_chunks)).strip()


def extract_categorized_keywords(text: str, max_keywords: int = 60) -> dict[str, list[str]]:
    lowered = text.lower()
    categorized: dict[str, list[str]] = {category: [] for category in CATEGORY_ORDER}

    for category, terms in SKILL_TAXONOMY.items():
        hits = [term for term in terms if _count_keyword(lowered, term) > 0]
        categorized[category] = sorted(hits, key=lambda term: (-_count_keyword(lowered, term), term))

    certifications = _extract_certifications(lowered)
    categorized["Business"] = _merge_unique(categorized["Business"], certifications)

    remaining = max_keywords
    limited: dict[str, list[str]] = {}
    for category in CATEGORY_ORDER:
        limited[category] = categorized[category][:remaining]
        remaining -= len(limited[category])
        if remaining <= 0:
            for empty_category in CATEGORY_ORDER[len(limited) :]:
                limited[empty_category] = []
            break

    return {category: limited.get(category, []) for category in CATEGORY_ORDER}


def _split_sections(text: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines()]
    sections: list[tuple[str, list[str]]] = [("job description", [])]

    for line in lines:
        if not line:
            sections[-1][1].append("")
            continue

        heading = _canonical_heading(line)
        if heading:
            sections.append((heading, []))
            continue
        sections[-1][1].append(line)

    return [(heading, "\n".join(content).strip()) for heading, content in sections if "\n".join(content).strip()]


def _canonical_heading(line: str) -> str | None:
    normalized = re.sub(r"[^a-zA-Z /'-]", "", line).strip().lower().rstrip(":")
    if len(normalized.split()) > 6:
        return None
    all_headings = CLEANER_REMOVE_HEADINGS + CLEANER_PRIORITY_HEADINGS
    if _heading_matches(normalized, all_headings):
        return normalized
    return None


def _heading_matches(heading: str, choices: tuple[str, ...]) -> bool:
    normalized = heading.lower().strip().rstrip(":")
    return any(normalized == choice or choice in normalized for choice in choices)


def _split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"(?:\n\s*){2,}|(?<=\.)\s+", text) if paragraph.strip()]


def _is_noise_paragraph(paragraph: str) -> bool:
    lowered = paragraph.lower()
    return any(ignored in lowered for ignored in IGNORED_LANGUAGE)


def _extract_certifications(text: str) -> list[str]:
    certifications: list[str] = []
    for pattern in CERTIFICATION_PATTERNS:
        for match in re.findall(pattern, text):
            certifications.append(match.strip())
    return sorted(set(certifications))


def _count_keyword(text: str, keyword: str) -> int:
    pattern = rf"(?<![a-zA-Z0-9]){re.escape(keyword)}s?(?![a-zA-Z0-9])"
    return len(re.findall(pattern, text.lower()))


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    merged = list(first)
    for item in second:
        if item not in merged:
            merged.append(item)
    return merged
