"""SQLite storage for extracted jobs."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "jobs.db"


JOB_COLUMNS = (
    "id",
    "title",
    "company",
    "location",
    "department",
    "employment_type",
    "apply_url",
    "raw_description",
    "cleaned_description",
    "source_type",
    "source_url",
    "scraped_at",
)


def init_db(db_path: Path = DATABASE_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                department TEXT,
                employment_type TEXT,
                apply_url TEXT NOT NULL UNIQUE,
                raw_description TEXT,
                cleaned_description TEXT,
                source_type TEXT,
                source_url TEXT,
                scraped_at TEXT NOT NULL
            )
            """
        )


def save_jobs(jobs: list[dict[str, Any]], db_path: Path = DATABASE_PATH) -> int:
    init_db(db_path)
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    saved = 0
    with sqlite3.connect(db_path) as connection:
        for job in jobs:
            connection.execute(
                """
                INSERT INTO jobs (
                    title, company, location, department, employment_type,
                    apply_url, raw_description, cleaned_description,
                    source_type, source_url, scraped_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(apply_url) DO UPDATE SET
                    title = excluded.title,
                    company = excluded.company,
                    location = excluded.location,
                    department = excluded.department,
                    employment_type = excluded.employment_type,
                    raw_description = excluded.raw_description,
                    cleaned_description = excluded.cleaned_description,
                    source_type = excluded.source_type,
                    source_url = excluded.source_url,
                    scraped_at = excluded.scraped_at
                """,
                (
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("department", ""),
                    job.get("employment_type", ""),
                    job.get("apply_url", ""),
                    job.get("raw_description", ""),
                    job.get("cleaned_description", ""),
                    job.get("source_type", ""),
                    job.get("source_url", ""),
                    scraped_at,
                ),
            )
            saved += 1
    return saved


def list_jobs(db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, title, company, location, department, employment_type,
                   apply_url, raw_description, cleaned_description,
                   source_type, source_url, scraped_at
            FROM jobs
            ORDER BY scraped_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_job(job_id: int, db_path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            f"SELECT {', '.join(JOB_COLUMNS)} FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None
