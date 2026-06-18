"""Resume and job matching logic."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.job_parser import ParsedJob
from app.services.resume_parser import ParsedResume


@dataclass(frozen=True)
class MatchResult:
    score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]


def score_resume_against_job(resume: ParsedResume, job: ParsedJob) -> MatchResult:
    resume_text = resume.raw_text.lower()
    keywords = job.keywords

    matched = [keyword for keyword in keywords if _contains_keyword(resume_text, keyword)]
    missing = [keyword for keyword in keywords if keyword not in matched]
    score = _calculate_score(matched, keywords)
    suggestions = build_suggestions(resume, missing, score)

    return MatchResult(
        score=score,
        matched_keywords=matched,
        missing_keywords=missing,
        suggestions=suggestions,
    )


def build_suggestions(resume: ParsedResume, missing_keywords: list[str], score: int) -> list[str]:
    suggestions: list[str] = []

    if missing_keywords:
        top_missing = ", ".join(missing_keywords[:8])
        suggestions.append(
            "Where accurate, mirror the job description language for these missing terms: "
            f"{top_missing}."
        )
    if not resume.sections.get("skills"):
        suggestions.append("Add a concise Skills section using only tools and capabilities you actually have.")
    if not resume.sections.get("summary"):
        suggestions.append("Add a 2-3 line summary tailored to the role without inventing experience.")
    if score < 70:
        suggestions.append(
            "Prioritize bullet rewrites that connect your existing experience to the role's required outcomes."
        )
    suggestions.append(
        "Keep claims evidence-based: do not add keywords unless they describe real experience, projects, or training."
    )

    return suggestions


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.lower().strip()
    if not normalized:
        return False
    pattern = rf"(?<!\w){re.escape(normalized)}s?(?!\w)"
    return bool(re.search(pattern, text))


def _calculate_score(matched: list[str], keywords: list[str]) -> int:
    if not keywords:
        return 0
    raw_score = round((len(matched) / len(keywords)) * 100)
    return max(0, min(100, raw_score))
