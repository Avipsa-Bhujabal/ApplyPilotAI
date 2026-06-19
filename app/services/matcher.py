"""Resume and job matching logic."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.services.job_parser import ParsedJob
from app.services.resume_parser import ParsedResume


EXPERIENCE_SIGNALS = (
    "built",
    "created",
    "delivered",
    "designed",
    "developed",
    "implemented",
    "improved",
    "led",
    "managed",
    "migrated",
    "optimized",
    "owned",
    "reduced",
    "shipped",
)


@dataclass(frozen=True)
class MatchResult:
    score: int
    keyword_match_score: int
    semantic_similarity_score: int
    experience_relevance_score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]
    semantic_model_used: bool


def score_resume_against_job(resume: ParsedResume, job: ParsedJob) -> MatchResult:
    resume_text = resume.raw_text.lower()
    keywords = job.keywords

    matched = [keyword for keyword in keywords if _contains_keyword(resume_text, keyword)]
    missing = [keyword for keyword in keywords if keyword not in matched]

    keyword_score = _calculate_keyword_score(matched, keywords)
    semantic_score, model_used = _semantic_similarity_score(resume.raw_text, job.cleaned_text)
    experience_score = _experience_relevance_score(resume, matched, keywords)
    overall_score = round((keyword_score * 0.4) + (semantic_score * 0.4) + (experience_score * 0.2))

    suggestions = build_suggestions(resume, missing, overall_score, model_used)

    return MatchResult(
        score=max(0, min(100, overall_score)),
        keyword_match_score=keyword_score,
        semantic_similarity_score=semantic_score,
        experience_relevance_score=experience_score,
        matched_keywords=matched,
        missing_keywords=missing,
        suggestions=suggestions,
        semantic_model_used=model_used,
    )


def build_suggestions(
    resume: ParsedResume,
    missing_keywords: list[str],
    score: int,
    semantic_model_used: bool,
) -> list[str]:
    suggestions: list[str] = []

    if missing_keywords:
        top_missing = ", ".join(missing_keywords[:8])
        suggestions.append(
            "Where accurate, mirror the job description language for these missing skills: "
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
    if not semantic_model_used:
        suggestions.append(
            "Install sentence-transformers and allow the all-MiniLM-L6-v2 model download for transformer semantic scoring."
        )
    suggestions.append(
        "Keep claims evidence-based: do not add keywords unless they describe real experience, projects, or training."
    )

    return suggestions


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized = keyword.lower().strip()
    if not normalized:
        return False
    pattern = rf"(?<![a-zA-Z0-9]){re.escape(normalized)}s?(?![a-zA-Z0-9])"
    return bool(re.search(pattern, text))


def _calculate_keyword_score(matched: list[str], keywords: list[str]) -> int:
    if not keywords:
        return 0
    return max(0, min(100, round((len(matched) / len(keywords)) * 100)))


def _semantic_similarity_score(resume_text: str, job_text: str) -> tuple[int, bool]:
    try:
        model = _load_sentence_transformer()
        embeddings = model.encode([resume_text, job_text], normalize_embeddings=True)
        similarity = float(embeddings[0] @ embeddings[1])
        return _similarity_to_score(similarity), True
    except Exception:
        return _fallback_similarity_score(resume_text, job_text), False


@lru_cache(maxsize=1)
def _load_sentence_transformer():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def _fallback_similarity_score(resume_text: str, job_text: str) -> int:
    resume_tokens = _meaningful_tokens(resume_text)
    job_tokens = _meaningful_tokens(job_text)
    if not resume_tokens or not job_tokens:
        return 0
    intersection = resume_tokens.intersection(job_tokens)
    union = resume_tokens.union(job_tokens)
    return round((len(intersection) / len(union)) * 100)


def _experience_relevance_score(resume: ParsedResume, matched: list[str], keywords: list[str]) -> int:
    experience_text = resume.sections.get("experience") or resume.raw_text
    lowered = experience_text.lower()
    signal_score = min(40, sum(1 for signal in EXPERIENCE_SIGNALS if signal in lowered) * 5)
    keyword_score = _calculate_keyword_score(
        [keyword for keyword in matched if _contains_keyword(lowered, keyword)],
        keywords,
    )
    years_score = 10 if re.search(r"\b\d+\+?\s+(?:years|yrs)\b", lowered) else 0
    return max(0, min(100, round((keyword_score * 0.5) + signal_score + years_score)))


def _similarity_to_score(similarity: float) -> int:
    normalized = (similarity + 1) / 2
    return max(0, min(100, round(normalized * 100)))


def _meaningful_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z+#./-]{2,}", text.lower())
    stop_words = {
        "and",
        "are",
        "for",
        "from",
        "that",
        "the",
        "this",
        "with",
        "you",
        "your",
    }
    return {token for token in tokens if token not in stop_words}
