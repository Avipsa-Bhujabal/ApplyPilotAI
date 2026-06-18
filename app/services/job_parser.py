"""Job description keyword extraction."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


STOP_WORDS = {
    "a",
    "about",
    "across",
    "after",
    "all",
    "also",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "candidate",
    "be",
    "by",
    "can",
    "description",
    "for",
    "from",
    "has",
    "have",
    "in",
    "including",
    "is",
    "it",
    "its",
    "job",
    "need",
    "needs",
    "of",
    "on",
    "or",
    "our",
    "required",
    "requirements",
    "responsibilities",
    "role",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
    "will",
    "you",
    "your",
}

COMMON_ATS_TERMS = {
    "agile",
    "analytics",
    "api",
    "automation",
    "aws",
    "azure",
    "business intelligence",
    "ci/cd",
    "communication",
    "crm",
    "dashboard",
    "data analysis",
    "docker",
    "etl",
    "excel",
    "git",
    "javascript",
    "jira",
    "kubernetes",
    "leadership",
    "machine learning",
    "python",
    "react",
    "reporting",
    "sql",
    "stakeholder",
    "tableau",
    "typescript",
}


@dataclass(frozen=True)
class ParsedJob:
    raw_text: str
    keywords: list[str]
    keyword_counts: dict[str, int]


def parse_job_description(text: str, max_keywords: int = 30) -> ParsedJob:
    cleaned = re.sub(r"\s+", " ", text).strip()
    keyword_counts = extract_keywords(cleaned, max_keywords=max_keywords)
    return ParsedJob(
        raw_text=cleaned,
        keywords=list(keyword_counts.keys()),
        keyword_counts=keyword_counts,
    )


def extract_keywords(text: str, max_keywords: int = 30) -> dict[str, int]:
    """Extract ATS-style keywords from a job description.

    The implementation is dependency-light for Windows friendliness: it combines
    known technical terms, repeated noun-like phrases, and meaningful single words.
    """
    lowered = text.lower()
    counts: Counter[str] = Counter()

    for term in COMMON_ATS_TERMS:
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        hits = len(re.findall(pattern, lowered))
        if hits:
            counts[term] += hits + 1

    tokens = [
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z+#./-]{1,}", lowered)
        if token not in STOP_WORDS and len(token) > 2
    ]
    counts.update(tokens)

    for phrase in _candidate_phrases(lowered):
        counts[phrase] += 2

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return dict(ranked[:max_keywords])


def _candidate_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    words = re.findall(r"[a-zA-Z][a-zA-Z+#./-]{1,}", text)
    filtered = [word for word in words if word not in STOP_WORDS]

    for size in (2, 3):
        for index in range(0, max(len(filtered) - size + 1, 0)):
            phrase = " ".join(filtered[index : index + size])
            if len(phrase) >= 8 and not any(part in STOP_WORDS for part in phrase.split()):
                phrases.append(phrase)

    return phrases
