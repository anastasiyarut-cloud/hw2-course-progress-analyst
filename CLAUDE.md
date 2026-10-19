# Project notes for Claude Code

Course Progress Analyst: a Streamlit dashboard + one Gemini data-analyst agent over the `course-db`
PostgreSQL database (online course platform). Homework project that will be submitted to a lecturer.

## Hard rules

- **Read-only database.** Only `SELECT` / `WITH ... SELECT`. Never modify or delete data — not via
  the app, not via the `course-db` MCP server.
- **Never overwrite, recreate or print `.env`.** It holds `GEMINI_API_KEY` and `DATABASE_URL`.
  Do not read secret values; check only variable names if needed. `.env.example` has placeholders only.
- **Keep `DECISIONS.md` up to date.** Every new decision made with the user gets a new row
  (`# | Topic | Proposed by | Proposal | Final decision | Why`; Final decision is one of
  "Accepted", "Changed by me", "Proposed by me" — written from the user's point of view).
  If Claude makes implementation choices the user hasn't reviewed, list them in a temporary
  "awaiting my review" section; once approved, move them into the main table and remove the section.
- **`GLOSSARY.md` is the semantic layer.** Dashboard metrics (`app.py`), `ENR_CTE` (`db.py`) and the
  agent's system prompt (`agent.py`) must match it exactly. Change all four together, and log the
  change in `DECISIONS.md`. Don't put a pending definition into code until the user approves it.
- Problems hit during the project go into the "Issues & resolutions" section of `DECISIONS.md`.
- Keep it simple: one agent, no extra frameworks.

## Layout

- `db.py` — read-only access (`conn.read_only = True` → `BEGIN READ ONLY`, plus
  `SET LOCAL statement_timeout`; the Neon pooler rejects startup options, so never pass
  `options=` to `psycopg.connect`), 200-row cap,
  `validate_select()` guard, and `ENR_CTE`: the shared `enr` definition that is prepended to every
  query, so the dashboard and the agent always use the same metric definitions.
- `agent.py` — Gemini (`google-genai`) with one tool `run_sql`; manual function-calling loop;
  model from `GEMINI_MODEL`, default `gemini-3.8-flash`. The system prompt documents tables and
  definitions — update it whenever a definition changes.
- `app.py` — KPIs, cumulative funnel chart (Altair), question box with "SQL used" expander.

## Agreed data definitions (details and reasoning in DECISIONS.md)

- Dates `enrolled_at` / `completed_at` are text in two formats: `YYYY-MM-DD` and `DD.MM.YYYY`.
- Progress: `LEAST(progress_pct, 100)` (277 rows exceed 100).
- **Completed** = completion date present AND `last_week_reached >= n_weeks` → 4,555.
  If completion date < enrollment date → `COMPLETED_PRIOR_CREDIT` (19 rows), still completed.
  The 356 rows with `completed_at` but no final week (date exactly 3 days before enrollment) are a
  recording error and are NOT completed — the user revisited this and confirmed it (DECISIONS.md #17,
  which supersedes #1). Never count completions with `completed_at IS NOT NULL`.
- **Certified** = `funnel_state = 'certified'` (4,555). Different definition from Completed; label
  them distinctly in the UI.
- Student = a user with at least one enrollment: `COUNT(DISTINCT user_id) FROM enr` → 37,529
  (DECISIONS.md #18, supersedes #4). User = anyone in `users` (40,000; 2,471 never enrolled).
- Completion rate = completed ÷ enrollments × 100, per enrollment (4.81%).
- Gemini free tier: 5 requests/min for gemini-3.8-flash; one question can use several requests.
- `funnel_state` is the CURRENT stage, ordered registered → viewed → explored → certified
  (verified with activity data). Funnel chart is cumulative ("reached at least").

## Commands (Windows PowerShell, from HW2)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The user's machine may block `Activate.ps1`; always give the direct `.venv\Scripts\python.exe` form.
