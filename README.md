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
