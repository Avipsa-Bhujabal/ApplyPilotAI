from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.services.job_parser import parse_job_description
from app.services.latex_generator import generate_resume_files
from app.services.matcher import score_resume_against_job
from app.services.pdf_extractor import extract_text_from_pdf_bytes
from app.services.resume_parser import parse_resume


st.set_page_config(page_title="ApplyPilotAI", page_icon="AP", layout="wide")


def main() -> None:
    st.title("ApplyPilotAI")
    st.caption("ATS resume matching and LaTeX resume generation. No application auto-submission.")

    left, right = st.columns(2)
    with left:
        uploaded_resume = st.file_uploader("Resume PDF", type=["pdf"])
        resume_text = ""
        if uploaded_resume:
            try:
                resume_text = extract_text_from_pdf_bytes(uploaded_resume.getvalue())
                if resume_text:
                    st.success("Resume PDF text extracted. Review it below before analyzing.")
                else:
                    st.warning("No selectable text found in this PDF. Try a text-based PDF or paste the resume text below.")
            except Exception as error:
                st.error(f"Could not read that PDF: {error}")

        resume_text = st.text_area(
            "Resume text extracted from PDF",
            value=resume_text,
            height=360,
            placeholder="Upload a text-based resume PDF, or paste the resume exactly as written.",
        )
    with right:
        job_text = st.text_area(
            "Job description text",
            height=360,
            placeholder="Paste the full job description, including requirements and responsibilities.",
        )

    analyze_clicked = st.button("Analyze match", type="primary", use_container_width=True)

    if analyze_clicked:
        if not resume_text.strip() or not job_text.strip():
            st.warning("Upload a resume PDF or paste resume text, then paste a job description to run the analysis.")
            return

        resume = parse_resume(resume_text)
        job = parse_job_description(job_text)
        result = score_resume_against_job(resume, job)

        st.session_state["resume"] = resume
        st.session_state["job"] = job
        st.session_state["match_result"] = result

    if "match_result" in st.session_state:
        render_results()


def render_results() -> None:
    resume = st.session_state["resume"]
    job = st.session_state["job"]
    result = st.session_state["match_result"]

    st.divider()
    score_col, matched_col, missing_col = st.columns(3)
    score_col.metric("Resume-job match score", f"{result.score}%")
    matched_col.metric("Matched keywords", len(result.matched_keywords))
    missing_col.metric("Missing keywords", len(result.missing_keywords))

    st.subheader("ATS keyword extraction")
    if job.keywords:
        st.write(", ".join(job.keywords))
    else:
        st.info("No keywords found. Try pasting a fuller job description.")

    keyword_left, keyword_right = st.columns(2)
    with keyword_left:
        st.subheader("Matched keywords")
        st.write(", ".join(result.matched_keywords) if result.matched_keywords else "None yet.")
    with keyword_right:
        st.subheader("Missing keywords")
        st.write(", ".join(result.missing_keywords) if result.missing_keywords else "No missing keywords detected.")

    st.subheader("ATS improvement suggestions")
    for suggestion in result.suggestions:
        st.write(f"- {suggestion}")

    st.subheader("LaTeX resume generation")
    st.write(
        "The generated resume uses only the resume text you provided plus ATS improvement notes. "
        "Review every change before sending it anywhere."
    )

    if st.button("Generate LaTeX and PDF", use_container_width=True):
        generated = generate_resume_files(resume, result.suggestions)
        st.success(generated.message)
        st.write(f"LaTeX file: `{generated.tex_path}`")
        st.write(f"PDF file: `{generated.pdf_path}`")
        render_downloads(generated.tex_path, generated.pdf_path)


def render_downloads(tex_path: Path, pdf_path: Path) -> None:
    if tex_path.exists():
        st.download_button(
            "Download .tex",
            data=tex_path.read_bytes(),
            file_name=tex_path.name,
            mime="application/x-tex",
            use_container_width=True,
        )
    if pdf_path.exists():
        st.download_button(
            "Download PDF",
            data=pdf_path.read_bytes(),
            file_name=pdf_path.name,
            mime="application/pdf",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
