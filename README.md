# ApplyPilotAI

ApplyPilotAI is currently focused on a Job Extraction MVP.

The app automatically extracts clean job data from configured public career pages, stores jobs in SQLite, and lets you inspect raw descriptions, cleaned descriptions, responsibilities, qualifications, and technical skills.

## Supported Sources

- Greenhouse job boards
- Lever job boards
- Public direct job URLs

The app intentionally does not scrape LinkedIn, Indeed, Glassdoor, login-gated pages, or captcha-protected pages.

## Features

- Automatic fetching from `data/job_sources.json`
- Job listing extraction:
  - title
  - company
  - location
  - department/team
  - employment type
  - apply URL
  - raw job description
  - cleaned job description
  - scraped timestamp
- SQLite storage at `database/jobs.db`
- Extracted jobs table
- Job detail inspector
- Responsibilities, qualifications, and technical skills extraction
- CSV export
- Resume matching:
  - upload a resume PDF or paste resume text in the sidebar
  - "Resume Match" tab scores the resume against the selected job (keyword, semantic, and experience scores)
  - matched/missing keywords and improvement suggestions
  - generate a LaTeX resume and PDF (compiled with `pdflatex` if installed, otherwise a ReportLab fallback)

## AI Agent

The **AI Agent** tab is a chat with a Claude-powered agent that uses the app's own features as tools. It decides which steps to take and runs them in a loop until it can answer.

Example requests:

- "Fetch jobs from https://boards.greenhouse.io/stripe for Stripe."
- "Which saved backend jobs best match my resume?"
- "Why is my score low for job 12, and what should I change?"
- "Generate a resume for the best match."

Tools available to the agent (`app/agent/tools.py`):

| Tool | What it does |
|---|---|
| `search_jobs` | Search saved jobs by keyword or company |
| `get_job` | Read one job's description and detected skills |
| `fetch_jobs` | Fetch a public Greenhouse/Lever board or job URL and save the jobs |
| `refresh_configured_sources` | Re-fetch everything in `data/job_sources.json` |
| `get_resume` | Read the resume loaded in the sidebar |
| `score_resume` | Score the resume against one job |
| `rank_jobs` | Score the resume against several jobs, best first |
| `generate_resume` | Generate a LaTeX + PDF resume for a job (downloadable in the tab) |

The agent loop lives in `app/agent/agent.py`. It needs an Anthropic API key:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
streamlit run streamlit_app.py
```

Set `ANTHROPIC_MODEL` to use a different Claude model (default `claude-opus-5-5`). The agent only fetches public pages and never submits applications.

## Setup

```powershell
cd D:\ApplyPilotAI
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```powershell
streamlit run streamlit_app.py
```

Then open the local URL shown by Streamlit, usually:

```text
http://localhost:8501
```

## Configure Sources

Add job boards or job URLs to `data/job_sources.json`:

```json
[
  {
    "company": "Example Company",
    "url": "https://boards.greenhouse.io/example",
    "source_type": "Greenhouse"
  },
  {
    "company": "Another Company",
    "url": "https://jobs.lever.co/another",
    "source_type": "Lever"
  }
]
```

Use `"Auto-detect"` for `source_type` if you want the app to infer Greenhouse, Lever, or Direct URL from the URL.

When the Streamlit app opens, it fetches configured sources automatically and shows the jobs table.

## Notes

- Start with Greenhouse and Lever URLs for the cleanest extraction.
- Direct URL extraction works best on public job-detail pages with readable HTML.
- The SQLite database is local and ignored by Git.
