"""Tools the ApplyPilot agent can call. Each wraps an existing service."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from app.services.jd_cleaner import extract_technical_skills
from app.services.job_fetcher import SOURCE_TYPES, fetch_and_store_jobs
from app.services.job_source_config import load_job_sources
from app.services.job_storage import get_job, list_jobs
from app.services.latex_generator import GeneratedResume, generate_resume_files
from app.services.matcher import MatchResult, score_resume_against_stored_job
from app.services.resume_parser import ParsedResume


MAX_RANKED_JOBS = 25
MAX_DESCRIPTION_CHARS = 6000


@dataclass
class AgentContext:
    """State the tools share with the UI for one session."""

    resume: ParsedResume | None = None
    match_cache: dict[tuple[int, str], MatchResult] = field(default_factory=dict)
    generated: dict[int, GeneratedResume] = field(default_factory=dict)


TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_jobs",
        "description": (
            "Search jobs already saved in the local database. Matches the query against title, "
            "company, location and department. Returns id, title, company, location and department."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Words to match; empty returns the newest jobs."},
                "company": {"type": "string", "description": "Optional exact company name filter."},
                "limit": {"type": "integer", "description": "Maximum results, 1-50. Default 20."},
            },
        },
    },
    {
        "name": "get_job",
        "description": "Get one saved job's details: metadata, cleaned description and detected technical skills.",
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "integer"}},
            "required": ["job_id"],
        },
    },
    {
        "name": "fetch_jobs",
        "description": (
            "Fetch jobs from a public Greenhouse board, Lever board, or a public job-detail URL and save them. "
            "LinkedIn, Indeed and Glassdoor are not supported. Returns how many jobs were saved."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name to store with the jobs."},
                "url": {"type": "string", "description": "Public board or job URL."},
                "source_type": {"type": "string", "enum": list(SOURCE_TYPES)},
            },
            "required": ["company", "url"],
        },
    },
    {
        "name": "refresh_configured_sources",
        "description": "Re-fetch every source listed in data/job_sources.json and save the jobs.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_resume",
        "description": "Get the user's parsed resume: name, contact, and sections. Errors if no resume is loaded.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "score_resume",
        "description": (
            "Score the user's resume against one saved job (0-100 overall, plus keyword, semantic and "
            "experience scores), with matched and missing keywords and suggestions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "integer"}},
            "required": ["job_id"],
        },
    },
    {
        "name": "rank_jobs",
        "description": (
            f"Score the user's resume against several saved jobs and return them best match first. "
            f"Filters work like search_jobs. Scores at most {MAX_RANKED_JOBS} jobs per call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "company": {"type": "string"},
                "limit": {"type": "integer", "description": f"Jobs to score, 1-{MAX_RANKED_JOBS}. Default 10."},
            },
        },
    },
    {
        "name": "generate_resume",
        "description": (
            "Generate a LaTeX resume and PDF from the user's resume, with notes for one saved job. "
            "Uses only facts already in the resume. The user can download the files in the app."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"job_id": {"type": "integer"}},
            "required": ["job_id"],
        },
    },
]


def run_tool(name: str, tool_input: dict[str, Any], context: AgentContext) -> str:
    """Run a tool and return its result as a JSON string. Raises on invalid input or failure."""
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool {name!r}.")
    return json.dumps(handler(tool_input, context), default=str)


def _search_jobs(tool_input: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    jobs = _filter_jobs(tool_input.get("query", ""), tool_input.get("company", ""))
    limit = _clamp(tool_input.get("limit", 20), 1, 50)
    return {"total_matches": len(jobs), "jobs": [_job_summary(job) for job in jobs[:limit]]}


def _get_job(tool_input: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    job = _require_job(tool_input)
    cleaned = job["cleaned_description"] or ""
    return {
        **_job_summary(job),
        "employment_type": job["employment_type"],
        "apply_url": job["apply_url"],
        "technical_skills": extract_technical_skills(cleaned),
        "description": cleaned[:MAX_DESCRIPTION_CHARS],
    }


def _fetch_jobs(tool_input: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    saved = fetch_and_store_jobs(
        str(tool_input["company"]),
        str(tool_input["url"]),
        str(tool_input.get("source_type") or "Auto-detect"),
    )
    return {"saved_jobs": saved}


def _refresh_configured_sources(tool_input: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    results = []
    for source in load_job_sources():
        try:
            saved = fetch_and_store_jobs(source["company"], source["url"], source["source_type"])
            results.append({"company": source["company"], "saved_jobs": saved})
        except Exception as error:
            results.append({"company": source["company"], "error": str(error)})
    return {"sources": results}


def _get_resume(tool_input: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    resume = _require_resume(context)
    return {
        "name": resume.name,
        "email": resume.email,
        "phone": resume.phone,
        "sections": resume.structured,
        "raw_text": resume.raw_text[:MAX_DESCRIPTION_CHARS],
    }


def _score_resume(tool_input: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    resume = _require_resume(context)
    job = _require_job(tool_input)
    return {**_job_summary(job), **_match_dict(score_job(resume, job, context))}


def _rank_jobs(tool_input: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    resume = _require_resume(context)
    jobs = _filter_jobs(tool_input.get("query", ""), tool_input.get("company", ""))
    limit = _clamp(tool_input.get("limit", 10), 1, MAX_RANKED_JOBS)
    ranked = []
    for job in jobs[:limit]:
        result = score_job(resume, job, context)
        ranked.append({**_job_summary(job), "score": result.score, "missing_keywords": result.missing_keywords[:8]})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {"jobs_matching_filters": len(jobs), "scored": len(ranked), "ranked": ranked}


def _generate_resume(tool_input: dict[str, Any], context: AgentContext) -> dict[str, Any]:
    resume = _require_resume(context)
    job = _require_job(tool_input)
    result = score_job(resume, job, context)
    generated = generate_resume_files(resume, result.suggestions)
    context.generated[job["id"]] = generated
    return {
        "job_id": job["id"],
        "tex_file": generated.tex_path.name,
        "pdf_file": generated.pdf_path.name,
        "message": generated.message,
    }


def score_job(resume: ParsedResume, job: dict[str, Any], context: AgentContext) -> MatchResult:
    """Score with a per-session cache; shared by the agent and the Resume Match tab."""
    cache_key = (job["id"], job["scraped_at"])
    if cache_key not in context.match_cache:
        context.match_cache[cache_key] = score_resume_against_stored_job(resume, job)
    return context.match_cache[cache_key]


def _filter_jobs(query: str, company: str) -> list[dict[str, Any]]:
    terms = [term for term in str(query or "").lower().split() if term]
    company = str(company or "").strip().lower()
    matches = []
    for job in list_jobs():
        if company and (job["company"] or "").lower() != company:
            continue
        haystack = " ".join(
            str(job[key] or "") for key in ("title", "company", "location", "department")
        ).lower()
        if all(term in haystack for term in terms):
            matches.append(job)
    return matches


def _require_job(tool_input: dict[str, Any]) -> dict[str, Any]:
    job_id = int(tool_input["job_id"])
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"No saved job with id {job_id}.")
    return job


def _require_resume(context: AgentContext) -> ParsedResume:
    if context.resume is None:
        raise ValueError("No resume is loaded. Ask the user to upload or paste their resume in the sidebar.")
    return context.resume


def _job_summary(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "department": job["department"],
    }


def _match_dict(result: MatchResult) -> dict[str, Any]:
    return {
        "score": result.score,
        "keyword_match_score": result.keyword_match_score,
        "semantic_similarity_score": result.semantic_similarity_score,
        "experience_relevance_score": result.experience_relevance_score,
        "matched_keywords": result.matched_keywords,
        "missing_keywords": result.missing_keywords,
        "suggestions": result.suggestions,
    }


def _clamp(value: Any, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = high
    return max(low, min(high, number))


_HANDLERS: dict[str, Callable[[dict[str, Any], AgentContext], dict[str, Any]]] = {
    "search_jobs": _search_jobs,
    "get_job": _get_job,
    "fetch_jobs": _fetch_jobs,
    "refresh_configured_sources": _refresh_configured_sources,
    "get_resume": _get_resume,
    "score_resume": _score_resume,
    "rank_jobs": _rank_jobs,
    "generate_resume": _generate_resume,
}
