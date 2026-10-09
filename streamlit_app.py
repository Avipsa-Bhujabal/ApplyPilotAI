from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from app.agent.agent import AgentEvent, agent_available, create_client, run_agent_turn
from app.agent.tools import AgentContext, score_job
from app.services.jd_cleaner import (
    extract_qualifications,
    extract_responsibilities,
    extract_technical_skills,
)
from app.services.job_fetcher import fetch_and_store_jobs
from app.services.job_source_config import load_job_sources
from app.services.job_storage import list_jobs
from app.services.latex_generator import GeneratedResume, generate_resume_files
from app.services.pdf_extractor import extract_text_from_pdf_bytes
from app.services.resume_parser import parse_resume


st.set_page_config(page_title="ApplyPilotAI Job Extractor", page_icon="AP", layout="wide")


def main() -> None:
    refresh_clicked = st.sidebar.button("Refresh configured sources", use_container_width=True)
    auto_fetch_configured_sources(force=refresh_clicked)
    render_resume_input()
    jobs_tab, agent_tab = st.tabs(["Jobs", "AI Agent"])
    with jobs_tab:
        render_jobs()
    with agent_tab:
        render_agent()


def _context() -> AgentContext:
    """Session state shared by the Jobs tab and the agent: resume, scores, generated files."""
    if "agent_context" not in st.session_state:
        st.session_state["agent_context"] = AgentContext()
    return st.session_state["agent_context"]


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
                total_saved += fetch_and_store_jobs(source["company"], source["url"], source["source_type"])
            except Exception as error:
                failures.append(f"{source.get('company', 'Unknown')}: {error}")

    if failures:
        st.sidebar.error("Some sources failed.")
        for failure in failures:
            st.sidebar.caption(failure)
    st.session_state["last_sources_key"] = sources_key
    st.sidebar.caption(f"Fetched {total_saved} job(s).")


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

    context = _context()
    if not resume_text:
        context.resume = None
        st.session_state.pop("resume_key", None)
        st.sidebar.caption("Add a resume to see match scores for each job.")
        return

    resume_key = hashlib.sha256(resume_text.encode("utf-8")).hexdigest()
    if st.session_state.get("resume_key") != resume_key:
        st.session_state["resume_key"] = resume_key
        context.resume = parse_resume(resume_text)
        context.match_cache.clear()
        context.generated.clear()

    resume = context.resume
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
    context = _context()
    resume = context.resume
    if resume is None:
        st.info("Upload or paste your resume in the sidebar to score it against this job.")
        return

    with st.spinner("Scoring resume against this job..."):
        result = score_job(resume, job, context)
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
        context.generated[job["id"]] = generated

    generated = context.generated.get(job["id"])
    if generated is not None:
        _render_downloads(generated, key_prefix=f"job_{job['id']}")


def render_agent() -> None:
    st.caption(
        "Ask the agent to find jobs, fetch a new Greenhouse/Lever board, rank jobs against your resume, "
        "or generate a resume for a job. It uses the same data as the Jobs tab."
    )
    if not agent_available():
        st.info("Set the ANTHROPIC_API_KEY environment variable (see .env.example) and restart the app to use the agent.")
        return

    history: list = st.session_state.setdefault("agent_history", [])
    transcript: list[dict] = st.session_state.setdefault("agent_transcript", [])
    if transcript and st.button("Clear conversation"):
        history.clear()
        transcript.clear()

    for entry in transcript:
        with st.chat_message(entry["role"]):
            for step in entry.get("steps", []):
                st.caption(step)
            st.markdown(entry["text"])

    prompt = st.chat_input("e.g. Which saved jobs best match my resume?")
    if not prompt:
        _render_agent_downloads()
        return

    transcript.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    steps: list[str] = []
    with st.chat_message("assistant"):
        with st.status("Working...", expanded=False) as status:

            def on_event(event: AgentEvent) -> None:
                label = {"tool_call": "Calling", "tool_result": "Finished", "tool_error": "Failed"}[event.kind]
                if event.kind == "tool_call":
                    steps.append(f"Tool: {event.tool_name}({event.detail})")
                elif event.kind == "tool_error":
                    steps.append(f"Tool {event.tool_name} failed: {event.detail}")
                status.update(label=f"{label} {event.tool_name}...")

            try:
                reply = run_agent_turn(create_client(), history, prompt, _context(), on_event)
                status.update(label="Done", state="complete")
            except Exception as error:
                reply = f"The agent hit an error: {error}"
                status.update(label="Error", state="error")
                # Drop the incomplete turn so the next request starts from a valid conversation.
                _truncate_to_last_complete_turn(history)
        for step in steps:
            st.caption(step)
        st.markdown(reply)
    transcript.append({"role": "assistant", "text": reply, "steps": steps})
    _render_agent_downloads()


def _render_agent_downloads() -> None:
    generated = _context().generated
    if not generated:
        return
    st.divider()
    st.markdown("**Generated resumes**")
    for job_id, files in generated.items():
        st.caption(f"Job {job_id}: {files.message}")
        _render_downloads(files, key_prefix=f"agent_{job_id}")


def _truncate_to_last_complete_turn(history: list) -> None:
    while history and not (history[-1]["role"] == "assistant" and _is_final_reply(history[-1])):
        history.pop()


def _is_final_reply(message: dict) -> bool:
    return not any(getattr(block, "type", None) == "tool_use" for block in message["content"])


def _render_downloads(generated: GeneratedResume, key_prefix: str) -> None:
    download_cols = st.columns(2)
    download_cols[0].download_button(
        "Download .tex",
        data=generated.tex_path.read_bytes(),
        file_name=generated.tex_path.name,
        mime="application/x-tex",
        use_container_width=True,
        key=f"{key_prefix}_tex",
    )
    download_cols[1].download_button(
        "Download PDF",
        data=generated.pdf_path.read_bytes(),
        file_name=generated.pdf_path.name,
        mime="application/pdf",
        use_container_width=True,
        key=f"{key_prefix}_pdf",
    )


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


if __name__ == "__main__":
    main()
