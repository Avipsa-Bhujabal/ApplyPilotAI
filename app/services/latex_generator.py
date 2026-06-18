"""LaTeX resume rendering and PDF generation."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.services.resume_parser import ParsedResume


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = PROJECT_ROOT / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output" / "generated_resumes"


LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


@dataclass(frozen=True)
class GeneratedResume:
    tex_path: Path
    pdf_path: Path
    used_latex: bool
    message: str


def generate_resume_files(resume: ParsedResume, suggestions: list[str]) -> GeneratedResume:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _slugify(resume.name or "resume")
    tex_path = OUTPUT_DIR / f"{slug}_{timestamp}.tex"
    pdf_path = OUTPUT_DIR / f"{slug}_{timestamp}.pdf"

    tex_content = render_latex(resume, suggestions)
    tex_path.write_text(tex_content, encoding="utf-8")

    if shutil.which("pdflatex"):
        _compile_latex(tex_path)
        expected_pdf = tex_path.with_suffix(".pdf")
        if expected_pdf.exists():
            return GeneratedResume(
                tex_path=tex_path,
                pdf_path=expected_pdf,
                used_latex=True,
                message="Generated LaTeX and compiled PDF with pdflatex.",
            )

    _write_fallback_pdf(pdf_path, resume, suggestions)
    return GeneratedResume(
        tex_path=tex_path,
        pdf_path=pdf_path,
        used_latex=False,
        message="Generated LaTeX and a fallback PDF. Install MiKTeX or TeX Live for native LaTeX compilation.",
    )


def render_latex(resume: ParsedResume, suggestions: list[str]) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["latex_escape"] = latex_escape
    template = env.get_template("resume.tex.j2")
    return template.render(resume=resume, suggestions=suggestions)


def latex_escape(value: str) -> str:
    return "".join(LATEX_REPLACEMENTS.get(char, char) for char in value or "")


def _compile_latex(tex_path: Path) -> None:
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", f"-output-directory={tex_path.parent}", tex_path.name],
        cwd=tex_path.parent,
        check=False,
        capture_output=True,
        text=True,
    )


def _write_fallback_pdf(pdf_path: Path, resume: ParsedResume, suggestions: list[str]) -> None:
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(str(pdf_path), pagesize=letter)
    story = []

    if resume.name:
        story.append(Paragraph(resume.name, styles["Title"]))
    contact = " | ".join(part for part in (resume.email, resume.phone) if part)
    if contact:
        story.append(Paragraph(contact, styles["Normal"]))
        story.append(Spacer(1, 12))

    for heading, content in resume.sections.items():
        if content:
            story.append(Paragraph(heading.title(), styles["Heading2"]))
            for line in content.splitlines():
                story.append(Paragraph(_escape_xml(line), styles["BodyText"]))
            story.append(Spacer(1, 8))

    if suggestions:
        story.append(Paragraph("ATS Improvement Notes", styles["Heading2"]))
        for suggestion in suggestions:
            story.append(Paragraph(f"- {_escape_xml(suggestion)}", styles["BodyText"]))

    document.build(story)


def _escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "resume"
