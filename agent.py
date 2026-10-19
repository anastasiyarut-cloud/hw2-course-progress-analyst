"""A single data-analyst agent: Gemini writes SELECT queries, we run them read-only, Gemini answers."""

import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from google import genai
from google.genai import types

from db import run_select

load_dotenv()

DEFAULT_MODEL = "gemini-3.8-flash"
MAX_STEPS = 6  # max rounds of tool calls per question

SYSTEM_PROMPT = """
You are a data analyst for an online course platform (similar to Coursera).
You answer questions about student course progress using a PostgreSQL database.
Use the run_sql tool to query the data. Never guess numbers - always query.

RULES
- Only write SELECT queries (you may start with WITH). The database is read-only.
- Prefer aggregated queries (COUNT, AVG, GROUP BY) and add LIMIT to row-level queries.
- Answer briefly in plain language, with the key numbers. Say which definition you used
  when it matters (for example "completed" or "progress").
- If a question cannot be answered from these tables, say so.

TABLES
`enr` - enrollments with cleaned columns. It is always available; use it instead of `enrollments`.
  enrollment_id, user_id, course_id, course_url, specialization_id, course_no,
  enrolled_date (date), completed_date (date), last_week_reached, n_weeks,
  progress_pct (raw, can exceed 100), progress_capped (progress capped at 100 - use this for averages),
  funnel_state ('registered' | 'viewed' | 'explored' | 'certified'), is_certified (0/1),
  is_completed (bool),
  completion_status ('COMPLETED' | 'COMPLETED_PRIOR_CREDIT' | 'NOT_COMPLETED')
  Do not use the raw text columns enrolled_at / completed_at.

users - user_id, signup_date (date), country, plan, persona, age_band, device_primary
dim_course - course_id, course_url, course, specialization_name, partner, level, domain,
  n_weeks, total_minutes, minutes_per_week, video_min, practice_min,
  review_score, n_reviews, mean_stars, pct_low
weekly_activity - enrollment_id, week_number, active_date (date), minutes_watched,
  quiz_attempts, quiz_score

JOINS: enr.user_id = users.user_id; enr.course_id = dim_course.course_id;
       enr.enrollment_id = weekly_activity.enrollment_id

DEFINITIONS (agreed with the project owner - must match GLOSSARY.md exactly)
- Enrollment: one row of `enr` (one student in one course). Count with COUNT(*).
- Completed: is_completed = true, i.e. a completion date exists AND the learner reached the
  final week (last_week_reached >= n_weeks). 4,555 enrollments.
  A completion date alone is NOT proof of completion: 356 enrollments have a completed_date but never
  reached the final week (date exactly 3 days before enrollment, avg progress 17.8%). That is a
  recording error; they are NOT completed (completion_status 'NOT_COMPLETED').
  Never count completions with "completed_date IS NOT NULL" - always use is_completed.
  completion_status 'COMPLETED_PRIOR_CREDIT' = completed (final week reached), but the completion date
  is before the enrollment date (audit conversion / transfer / LMS sync anomaly). 19 enrollments.
  It still counts as completed. It never turns an enrollment without the final week into a completion.
- Certified: funnel_state = 'certified' (is_certified = 1). A separate definition from Completed,
  even though the counts happen to match in this data.
- Completion rate: 100.0 * COUNT(*) FILTER (WHERE is_completed) / COUNT(*) - per enrollment, in %.
- Average progress: AVG(progress_capped), per enrollment, in %.
- User: anyone in the users table (40,000), including 2,471 who signed up but never enrolled.
- Student: a user with at least one enrollment. Count with COUNT(DISTINCT user_id) FROM enr (37,529).
  One student can have many enrollments (avg 2.52, max 10). Use Student, not User, for questions about
  learners; for per-student metrics, group by user_id first.
- Funnel stages are ordered registered -> viewed -> explored -> certified. funnel_state is the
  CURRENT stage. "Reached at least stage X" = that stage plus all later stages.
  Drop % between two stages = 100 * (1 - reached(stage) / reached(previous stage)).
  registered = enrolled but no activity; viewed = progress 1-49%; explored = 50-99%;
  certified = finished the final week.
""".strip()

RUN_SQL = types.FunctionDeclaration(
    name="run_sql",
    description=(
        "Run one read-only PostgreSQL SELECT query and return the result rows "
        "(max 200 rows). The table `enr` is always available."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={"query": types.Schema(type=types.Type.STRING, description="A single SELECT query")},
        required=["query"],
    ),
)


@dataclass
class QueryLog:
    sql: str
    rows: int | None = None
    error: str | None = None


@dataclass
class AgentAnswer:
    text: str
    queries: list[QueryLog] = field(default_factory=list)


def _run_tool(sql: str, log: list[QueryLog]) -> dict:
    try:
        df, truncated = run_select(sql)
    except Exception as exc:  # the error goes back to Gemini so it can fix the query
        log.append(QueryLog(sql=sql, error=str(exc)))
        return {"error": str(exc)}
    log.append(QueryLog(sql=sql, rows=len(df)))
    rows = json.loads(df.to_json(orient="records", date_format="iso"))
    return {"columns": list(df.columns), "rows": rows, "truncated": truncated}


def ask(question: str) -> AgentAnswer:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to the .env file.")
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=[RUN_SQL])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0,
    )

    contents = [types.Content(role="user", parts=[types.Part(text=question)])]
    log: list[QueryLog] = []
    for _ in range(MAX_STEPS):
        response = client.models.generate_content(model=model, contents=contents, config=config)
        calls = response.function_calls
        if not calls:
            return AgentAnswer(text=response.text or "(no answer)", queries=log)
        contents.append(response.candidates[0].content)
        parts = [
            types.Part.from_function_response(name=call.name, response=_run_tool(call.args.get("query", ""), log))
            for call in calls
        ]
        contents.append(types.Content(role="user", parts=parts))
    return AgentAnswer(text="I could not finish the analysis within the step limit. Try a simpler question.", queries=log)
