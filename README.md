# Course Progress Analyst

A simple Data Analyst Agent for an online course platform. A Streamlit dashboard shows key
progress metrics and a learning funnel, and lets you ask questions in plain English. A single
Gemini agent turns each question into read-only SQL, runs it, and answers.

All design decisions and the reasoning behind them are in **[DECISIONS.md](DECISIONS.md)**.
Every term and metric (Student, Enrollment, Completed, Certified, …) is defined in
**[GLOSSARY.md](GLOSSARY.md)** — the dashboard and the agent use exactly these definitions.

## What the dashboard shows

- **Total enrollments**, with the number of students (users with at least one enrollment)
- **Average progress** (each enrollment capped at 100%)
- **Completed** enrollments (completion date present and final week reached)
- **Learning funnel**: enrollments that reached at least each stage
  (Registered → Viewed → Explored → Certified), with the % drop between stages
- **Ask the analyst**: a question box, the agent's answer, and the SQL it ran

## What the agent does

The agent is a single Gemini model (`google-genai`, default `gemini-3.8-flash`) with one tool,
`run_sql`. For each question:

1. Gemini reads the question together with a system prompt that describes the tables and the
   agreed definitions from [GLOSSARY.md](GLOSSARY.md).
2. It writes one or more read-only `SELECT` queries and calls `run_sql`.
3. The app checks each query, runs it on the database in read-only mode, and sends the rows back.
4. Gemini answers in plain English with the key numbers. The dashboard also shows the SQL it ran,
   so every answer can be checked.

## Data it uses

A PostgreSQL database of an online course platform (the `course-db` database, also connected to
Claude Code through MCP). The agent and the dashboard use four tables:

| Table | Contents |
|---|---|
| `enrollments` | One row per student per course: enrollment and completion dates, progress, weeks reached, funnel stage, certificate flag (94,705 rows) |
| `users` | Users: signup date, country, plan, persona, age band, main device (40,000 rows) |
| `dim_course` | Courses: name, specialization, partner, level, domain, length, reviews |
| `weekly_activity` | Weekly learning activity: minutes watched, quiz attempts, quiz scores |

Data-quality problems (mixed date formats, progress above 100%, invalid completion dates) are
handled by shared definitions in `db.py`; see the *Data quality findings* in
[DECISIONS.md](DECISIONS.md#data-quality-findings).

## Project files

| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard |
| `agent.py` | The Gemini agent (one tool: `run_sql`) |
| `db.py` | Read-only database access and the shared metric definitions |
| `requirements.txt` | Python packages |
| `.env.example` | Template for the secrets file |
| `DECISIONS.md` | Decision log |
| `GLOSSARY.md` | Definitions of all terms and metrics (semantic layer) |
| `CLAUDE.md` | Project notes for Claude Code |

## Setup (Windows PowerShell)

Open PowerShell and go to the project folder:

```powershell
cd "C:\Users\achesnokova\Documents\AI for Data Analytics\HW2"
```

### 1. Create the virtual environment (once)

```powershell
python -m venv .venv
```

### 2. Install the packages (once)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Secrets file

The app reads `GEMINI_API_KEY` and `DATABASE_URL` from a `.env` file in this folder.

> **New users only** – if you do not have a `.env` file yet, create it from the template and then
> open it and fill in your own values:
>
> ```powershell
> Copy-Item .env.example .env
> ```
>
> **If you already have a `.env`, skip this step** – the command would overwrite your existing file.

### 4. Run the dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The dashboard opens in your browser at http://localhost:8501. Stop it with `Ctrl+C` in PowerShell.

> On the Gemini free tier only a few requests per minute are allowed. If the dashboard says the
> limit was reached, wait about a minute and ask again.

### If `Activate.ps1` is blocked (execution policy)

The commands above call the venv's Python directly (`.\.venv\Scripts\python.exe -m ...`), so
activation is **not** needed, and they work even when PowerShell blocks scripts. If you prefer to
activate the venv:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

If PowerShell says *"running scripts is disabled on this system"*, don't activate — use the
`.\.venv\Scripts\python.exe -m ...` commands from steps 2 and 4 instead.

## Example questions

- Which course level has the highest completion rate?
- What is the average progress by country? Show the top 5.
- How many minutes per week do learners who completed a course watch on average?
- Which domain has the biggest drop from Viewed to Explored?

## Safety: read-only by design

The app can never change the data:

1. Every query runs in a **read-only transaction**, so PostgreSQL itself refuses any write.
2. Every query is checked: only a **single `SELECT`** (optionally starting with `WITH`) is allowed,
   and write keywords such as `INSERT`, `UPDATE`, `DELETE`, `DROP` are rejected.
3. Queries time out after **15 seconds** and return at most **200 rows**.

Secrets live only in `.env`, which is excluded from git by `.gitignore`.
