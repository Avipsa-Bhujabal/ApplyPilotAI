from __future__ import annotations

import hashlib
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from app.services.jd_cleaner import (
    extract_qualifications,
    extract_responsibilities,
    extract_technical_skills,
)
from app.services.job_extractors import (
    extract_direct_url_jobs,
    extract_greenhouse_jobs,
    extract_lever_jobs,
)
from app.services.job_parser import parse_job_description
from app.services.job_source_config import load_job_sources
from app.services.job_storage import list_jobs, save_jobs
from app.services.latex_generator import generate_resume_files
from app.services.matcher import MatchResult, score_resume_against_job
from app.services.pdf_extractor import extract_text_from_pdf_bytes
from app.services.resume_parser import ParsedResume, parse_resume


st.set_page_config(page_title="ApplyPilotAI Job Extractor", page_icon="AP", layout="wide")


def main() -> None:
    refresh_clicked = st.sidebar.button("Refresh configured sources", use_container_width=True)
    auto_fetch_configured_sources(force=refresh_clicked)
    render_resume_input()
    render_jobs()


def auto_fetch_configured_sources(force: bool = False) -> None:
    try:
        sources = load_job_sources()
    except Exception as error:
        st.error(f"Could not read data/job_sources.json: {error}")
        return

    if not sources:
        return

    sources_key = "|".join(f"{source['company']}:{source['url']}:{source['source_type']}" for source in sources)
    if not force and st.session_state.get("last_sources_key") == sources_key:
        return

    total_saved = 0
    failures = []
    with st.spinner("Fetching configured job sources..."):
        for source in sources:
            try:
                source_url = source["url"]
                if not _looks_like_url(source_url):
                    raise ValueError("Invalid URL.")
                source_type = _resolve_source_type(source_url, source["source_type"])
                saved_count = run_extraction(source["company"], source_url, source_type, show_status=False)
                total_saved += saved_count or 0
            except Exception as error:
                failures.append(f"{source.get('company', 'Unknown')}: {error}")

    if failures:
        st.sidebar.error("Some sources failed.")
        for failure in failures:
            st.sidebar.caption(failure)
    st.session_state["last_sources_key"] = sources_key
    st.sidebar.caption(f"Fetched {total_saved} job(s).")


def run_extraction(
    company_name: str,
    source_url: str,
    source_type: str,
    show_status: bool = True,
) -> int | None:
    try:
        extractor = {
            "Greenhouse": extract_greenhouse_jobs,
            "Lever": extract_lever_jobs,
            "Direct URL": extract_direct_url_jobs,
        }[source_type]
        jobs = extractor(company_name, source_url)
        saved_count = save_jobs(jobs)
        if show_status:
            st.success(f"Extracted and stored {saved_count} job(s) from {source_type}.")
        return saved_count
    except Exception as error:
        if show_status:
            st.error(f"Could not extract jobs: {error}")
        else:
            raise
        return None


def render_resume_input() -> None:
    st.sidebar.divider()
    st.sidebar.subheader("Your resume")
    uploaded = st.sidebar.file_uploader("Upload resume PDF", type=["pdf"])
    pasted = st.sidebar.text_area("Or paste resume text", height=160)

    resume_text = ""
    if uploaded is not None:
        try:
            resume_text = extract_text_from_pdf_bytes(uploaded.getvalue())
        except Exception as error:
            st.sidebar.error(f"Could not read PDF: {error}")
        if not resume_text:
            st.sidebar.warning("No text found in that PDF. Scanned resumes are not supported; paste the text instead.")
    if not resume_text:
        resume_text = pasted.strip()

    if not resume_text:
        st.session_state.pop("resume", None)
        st.sidebar.caption("Add a resume to see match scores for each job.")
        return

    resume_key = hashlib.sha256(resume_text.encode("utf-8")).hexdigest()
    if st.session_state.get("resume_key") != resume_key:
        st.session_state["resume_key"] = resume_key
        st.session_state["resume"] = parse_resume(resume_text)
        st.session_state["match_cache"] = {}
        st.session_state["generated_resumes"] = {}

    resume: ParsedResume = st.session_state["resume"]
    st.sidebar.success(f"Resume loaded{': ' + resume.name if resume.name else ''}.")


def render_jobs() -> None:
    jobs = list_jobs()
    if not jobs:
        st.info("No jobs found yet. Add sources to data/job_sources.json and refresh the page.")
        return

    table_rows = [
        {
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "department": job["department"],
            "employment_type": job["employment_type"],
            "source_type": job["source_type"],
            "scraped_at": job["scraped_at"],
            "apply_url": job["apply_url"],
        }
        for job in jobs
    ]
    df = pd.DataFrame(table_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button(
        "Export CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="extracted_jobs.csv",
        mime="text/csv",
        use_container_width=True,
    )

    selected_id = st.selectbox(
        "Select a job to inspect",
        options=[job["id"] for job in jobs],
        format_func=lambda job_id: _job_label(jobs, job_id),
    )
    selected_job = next(job for job in jobs if job["id"] == selected_id)
    render_job_detail(selected_job)


def render_job_detail(job: dict) -> None:
    st.subheader(job["title"] or "Selected job")
    meta_cols = st.columns(4)
    meta_cols[0].metric("Company", job["company"] or "Unknown")
    meta_cols[1].metric("Location", job["location"] or "Unknown")
    meta_cols[2].metric("Department", job["department"] or "Unknown")
    meta_cols[3].metric("Type", job["employment_type"] or "Unknown")

    st.link_button("Open apply URL", job["apply_url"], use_container_width=True)

    cleaned = job["cleaned_description"] or ""
    detail_tabs = st.tabs(
        [
            "Cleaned Description",
            "Raw Description",
            "Responsibilities",
            "Qualifications",
            "Technical Skills",
            "Resume Match",
        ]
    )
    with detail_tabs[0]:
        st.text_area("Cleaned job description", cleaned, height=320)
    with detail_tabs[1]:
        st.text_area("Raw job description", job["raw_description"] or "", height=320)
    with detail_tabs[2]:
        _render_list(extract_responsibilities(cleaned))
    with detail_tabs[3]:
        _render_list(extract_qualifications(cleaned))
    with detail_tabs[4]:
        skills = extract_technical_skills(cleaned)
        st.write(", ".join(skills) if skills else "No technical skills detected.")
    with detail_tabs[5]:
        render_resume_match(job)


def render_resume_match(job: dict) -> None:
    resume: ParsedResume | None = st.session_state.get("resume")
    if resume is None:
        st.info("Upload or paste your resume in the sidebar to score it against this job.")
        return

    result = _match_resume_to_job(resume, job)
    score_cols = st.columns(4)
    score_cols[0].metric("Overall match", f"{result.score}/100")
    score_cols[1].metric("Keyword match", f"{result.keyword_match_score}/100")
    score_cols[2].metric("Semantic similarity", f"{result.semantic_similarity_score}/100")
    score_cols[3].metric("Experience relevance", f"{result.experience_relevance_score}/100")
    if not result.semantic_model_used:
        st.caption("Semantic similarity uses word overlap because the sentence-transformers model is unavailable.")

    keyword_cols = st.columns(2)
    with keyword_cols[0]:
        st.markdown("**Matched keywords**")
        st.write(", ".join(result.matched_keywords) if result.matched_keywords else "None.")
    with keyword_cols[1]:
        st.markdown("**Missing keywords**")
        st.write(", ".join(result.missing_keywords) if result.missing_keywords else "None.")

    st.markdown("**Suggestions**")
    _render_list(result.suggestions)

    if st.button("Generate resume (LaTeX + PDF)", key=f"generate_{job['id']}", use_container_width=True):
        try:
            generated = generate_resume_files(resume, result.suggestions)
        except Exception as error:
            st.error(f"Could not generate resume: {error}")
            return
        st.session_state.setdefault("generated_resumes", {})[job["id"]] = generated

    generated = st.session_state.get("generated_resumes", {}).get(job["id"])
    if generated is not None:
        st.caption(generated.message)
        download_cols = st.columns(2)
        download_cols[0].download_button(
            "Download .tex",
            data=generated.tex_path.read_bytes(),
            file_name=generated.tex_path.name,
            mime="application/x-tex",
            use_container_width=True,
        )
        download_cols[1].download_button(
            "Download PDF",
            data=generated.pdf_path.read_bytes(),
            file_name=generated.pdf_path.name,
            mime="application/pdf",
            use_container_width=True,
        )


def _match_resume_to_job(resume: ParsedResume, job: dict) -> MatchResult:
    cache: dict = st.session_state.setdefault("match_cache", {})
    cache_key = (job["id"], job["scraped_at"])
    if cache_key not in cache:
        with st.spinner("Scoring resume against this job..."):
            parsed_job = parse_job_description(job["raw_description"] or job["cleaned_description"] or "")
            cache[cache_key] = score_resume_against_job(resume, parsed_job)
    return cache[cache_key]


def _render_list(items: list[str]) -> None:
    if not items:
        st.write("No items detected.")
        return
    for item in items:
        st.write(f"- {item}")


def _job_label(jobs: list[dict], job_id: int) -> str:
    job = next((item for item in jobs if item["id"] == job_id), None)
    if not job:
        return str(job_id)
    return f"{job['title']} - {job['company']}"


def _looks_like_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _resolve_source_type(source_url: str, source_type: str) -> str:
    if source_type != "Auto-detect":
        return source_type

    host = urlparse(source_url).netloc.lower()
    if "greenhouse.io" in host:
        return "Greenhouse"
    if "lever.co" in host:
        return "Lever"
    return "Direct URL"


if __name__ == "__main__":
    main()
