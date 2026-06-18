# ApplyPilotAI

ApplyPilotAI is a Windows-friendly MVP for comparing a pasted resume against a pasted job description, extracting ATS keywords, showing a match score, identifying missing keywords, suggesting factual improvements, and generating a Jinja2-rendered LaTeX resume with PDF output.

The app does not auto-submit applications and does not invent resume facts.

## Features

- Resume text input
- Job description text input
- ATS keyword extraction
- Resume-job match score
- Missing keyword detection
- ATS improvement suggestions
- LaTeX resume generation with Jinja2 templates
- PDF output in `output/generated_resumes/`
- Streamlit dashboard

## Project Structure

```text
app/
  services/
    job_parser.py
    resume_parser.py
    matcher.py
    latex_generator.py
templates/
data/
output/generated_resumes/
streamlit_app.py
README.md
requirements.txt
```

## Setup

From the project folder:

```powershell
cd D:\Projects\ApplyPilotAI
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If your repository is located at `D:\ApplyPilotAI` in this environment, use that path instead.

## Run

```powershell
streamlit run streamlit_app.py
```

Open the local Streamlit URL shown in the terminal.

## PDF Generation

ApplyPilotAI always writes a `.tex` file to `output/generated_resumes/`.

For native LaTeX PDF compilation, install MiKTeX or TeX Live and make sure `pdflatex` is available on your `PATH`.

If `pdflatex` is not installed, the app creates a simple fallback PDF with ReportLab so the MVP remains runnable on Windows.

## Notes

- Paste only resume facts that are true.
- Treat missing keywords as review prompts, not instructions to fabricate experience.
- Review generated files before sharing them with employers.
