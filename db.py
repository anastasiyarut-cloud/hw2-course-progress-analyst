"""Read-only access to the course database.

Safety layers (see DECISIONS.md):
1. Every query runs in a READ ONLY transaction, so PostgreSQL itself rejects
   any write.
2. validate_select() only lets through a single SELECT / WITH statement.
3. Every query has a timeout and results are capped at MAX_ROWS.
"""

import os
import re

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

MAX_ROWS = 200
TIMEOUT_MS = 15_000

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|"
    r"copy|call|vacuum|reindex|lock|set|reset|refresh|execute|prepare)\b",
    re.IGNORECASE,
)

# Shared definitions used by the dashboard AND the agent, so both give the same numbers.
# enrolled_at / completed_at are text in two formats: YYYY-MM-DD and DD.MM.YYYY.
ENR_CTE = r"""
enr_dates AS (
    SELECT e.*,
        CASE WHEN e.enrolled_at ~ '^\d{2}\.\d{2}\.\d{4}$' THEN to_date(e.enrolled_at, 'DD.MM.YYYY')
             WHEN e.enrolled_at ~ '^\d{4}-\d{2}-\d{2}$'   THEN to_date(e.enrolled_at, 'YYYY-MM-DD')
        END AS enrolled_date,
        CASE WHEN e.completed_at ~ '^\d{2}\.\d{2}\.\d{4}$' THEN to_date(e.completed_at, 'DD.MM.YYYY')
             WHEN e.completed_at ~ '^\d{4}-\d{2}-\d{2}$'   THEN to_date(e.completed_at, 'YYYY-MM-DD')
        END AS completed_date,
        LEAST(e.progress_pct, 100) AS progress_capped
    FROM enrollments e
),
-- Definitions follow GLOSSARY.md. Completed = completion date AND final week reached (DECISIONS.md #17):
-- 356 rows have a completed_at but no final week (date 3 days before enrollment) and are NOT completed.
-- COMPLETED_PRIOR_CREDIT applies only to completed rows (#3).
-- Student = a user with at least one enrollment: COUNT(DISTINCT user_id) FROM enr (#18).
enr AS (
    SELECT d.*,
        (d.completed_date IS NOT NULL AND d.last_week_reached >= d.n_weeks) AS is_completed,
        CASE WHEN NOT (d.completed_date IS NOT NULL AND d.last_week_reached >= d.n_weeks) THEN 'NOT_COMPLETED'
             WHEN d.completed_date < d.enrolled_date THEN 'COMPLETED_PRIOR_CREDIT'
             ELSE 'COMPLETED'
        END AS completion_status
    FROM enr_dates d
)
"""


def validate_select(sql: str) -> str:
    """Return a cleaned query, or raise ValueError if it is not a single read-only SELECT."""
    cleaned = re.sub(r"--[^\n]*", " ", sql)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("Empty query.")
    if ";" in cleaned:
        raise ValueError("Only one statement is allowed.")
    if not re.match(r"^(select|with)\b", cleaned, re.IGNORECASE):
        raise ValueError("Only SELECT queries (optionally starting with WITH) are allowed.")
    if re.match(r"^with\s+recursive\b", cleaned, re.IGNORECASE):
        raise ValueError("WITH RECURSIVE is not supported.")
    match = FORBIDDEN.search(cleaned)
    if match:
        raise ValueError(f"Keyword '{match.group(0)}' is not allowed in a read-only query.")
    return cleaned


def with_enr(sql: str) -> str:
    """Prepend the shared `enr` CTE so queries can use it like a table."""
    if re.match(r"^with\b", sql, re.IGNORECASE):
        return "WITH " + ENR_CTE + ",\n" + sql[4:].lstrip()
    return "WITH " + ENR_CTE + "\n" + sql


def run_select(sql: str, max_rows: int = MAX_ROWS) -> tuple[pd.DataFrame, bool]:
    """Run a read-only query. Returns (dataframe, truncated)."""
    query = with_enr(validate_select(sql))
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is missing. Add it to the .env file.")
    # Neon's connection pooler rejects startup options, so read-only mode and the timeout
    # are set per transaction instead: read_only=True makes psycopg send BEGIN READ ONLY.
    with psycopg.connect(url, connect_timeout=10) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL statement_timeout = {TIMEOUT_MS}")
            cur.execute(query)
            columns = [c.name for c in cur.description]
            rows = cur.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    return pd.DataFrame(rows[:max_rows], columns=columns), truncated
