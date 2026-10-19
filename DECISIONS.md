# Decision Log

This file records the decisions made while building the Course Progress Analyst, who proposed
each one, and why. It is updated whenever a new decision is made.

## Setup (done outside the project)

- Installed Node.js (portable ZIP, no admin rights) and the Claude Code CLI.
- Added the `course-db` MCP server with user scope (`-s user`), because the VS Code panel did not
  pick up the local scope.
- Created a Gemini API key and stored it in `.env`.

## Decisions

"Proposed by": **Claude** (Claude Code) or **Me**.
"Final decision": **Accepted** (Claude's proposal kept), **Changed by me** (I changed Claude's
proposal), **Proposed by me** (my own requirement), and once **Changed by me after data check**
(I revised my own earlier decision because of evidence in the data — #17).
A row marked **Superseded** is kept for the record but no longer applies.

| # | Topic | Proposed by | Proposal | Final decision | Why |
|---|---|---|---|---|---|
| 1 | Definition of "completed" | Claude | Count completed as `is_certified = 1` (4,555). | **Superseded by #17.** Changed by me: completed = `completed_at IS NOT NULL`. | Completion means all academic requirements were met on a specific date. A certificate is an administrative confirmation that also depends on non-learning factors (payment, identity verification, processing delays), so it should not define completion. |
| 2 | Validity of completion dates | Claude | A check showed that 356 enrollments with a `completed_at` are not certified and contradict the data: 356 completed before they enrolled (first reported as 336, because dates were then compared as text — corrected after parsing the dates), none reached the final week, 355 have progress < 100%, 120 never had any activity. Proposed option B: completion date present **and** final week reached (plus a date check), instead of option A (all 4,911 rows). | Accepted (option B). Confirmed and formally recorded in #17. | Keeps my learning-based definition from #1 but excludes rows that cannot be real completions. |
| 3 | Completion date before enrollment date | Me | With dates parsed correctly, option B with the date check gave 4,536, not 4,555 (Claude corrected its earlier number, which came from comparing dates as text). The 19 excluded enrollments are certified, reached the final week, and have a completion date exactly 3 days before enrollment. Claude proposed dropping the date check. | Proposed by me: compute `delta = completion_date − enrollment_date`; if `delta < 0`, classify as **COMPLETED_PRIOR_CREDIT**. These still count as completed (total 4,555 = 4,536 COMPLETED + 19 COMPLETED_PRIOR_CREDIT). | A negative delta can come from audit-to-paid conversions, session transfers, or LMS sync anomalies. It does not invalidate the student status or the proof of completion. The rule applies only to enrollments whose completion is confirmed by the other signals (see #17). |
| 4 | Definition of "student" | Me | — | **Superseded by #18.** Proposed by me: `is_student = True` when an enrollment date is present. | Anyone with an enrollment date is a Coursera student. In this data all 94,705 enrollments qualify (37,529 distinct users). |
| 5 | Progress above 100% | Claude | Cap `progress_pct` at 100 when averaging (277 rows go up to 104). | Accepted. | A value over 100% is an LMS tracking anomaly (extra credit, retaken activities, sync errors). Completion is a yes/no state of meeting all core requirements, not a score that can exceed full mastery. |
| 6 | Mixed date formats | Claude | `enrolled_at` / `completed_at` are text in two formats (90,919 `YYYY-MM-DD`, 3,786 `DD.MM.YYYY`); parse both into real dates before any date logic. | Accepted. | Comparing dates as text gives wrong results (this is exactly what caused the wrong number in #3). |
| 7 | Funnel stage order | Me | — | Proposed by me: verify the stage order in the data instead of assuming it. | `funnel_state` is the current stage of each enrollment, so its meaning must be checked. Result: the order registered → viewed → explored → certified is confirmed. Registered enrollments have 0% weekly activity; viewed = 1–49% progress (≈1 week active); explored = 50–99% (≈2.2 weeks); certified = 100% and final week reached (≈3.8 weeks). Minutes watched and quiz attempts rise at each stage. |
| 8 | Funnel visualization | Claude | Bar chart of enrollments per `funnel_state`. | Changed by me: a **cumulative** funnel — enrollments that reached *at least* each stage, with the % drop between steps. | Each enrollment stores only its current stage, so a plain count per stage is not a funnel. Result: 94,705 → 61,619 (−34.9%) → 10,397 (−83.1%) → 4,555 (−56.2%). |
| 9 | Chart and card labels | Me | — | Proposed by me: last funnel stage labelled **"Certified"**, metric card labelled **"Completed"**. | They are different definitions. Clear labels (plus a caption) stop matching or differing numbers from looking like a bug. |
| 10 | Python environment | Claude | Create a new `.venv` inside HW2 instead of using the parent folder's `.venv` (which lacked the packages). | Accepted. | Keeps the project self-contained and reproducible. |
| 11 | Secrets handling | Me | — | Proposed by me: secrets only in `.env` (never hardcoded); `.env.example` with placeholders only; `.gitignore` excludes `.env` and `.venv`; my existing `.env` is never overwritten; the README marks `Copy-Item .env.example .env` as a step for new users only. | Keeps keys and passwords out of code and out of git, and protects my working configuration. |
| 12 | PowerShell execution policy | Me | — | Proposed by me: README shows commands that run the venv's Python directly (`.\.venv\Scripts\python.exe -m ...`), with activation as an optional alternative. | My laptop may block `Activate.ps1`. |
| 13 | CLAUDE.md | Me | — | Proposed by me: a `CLAUDE.md` with project notes for future Claude Code sessions. | Future sessions keep the agreed definitions and rules without re-deriving them. |
| 14 | Decision log | Me | — | Proposed by me: this `DECISIONS.md`, linked from the README and updated with every new decision. | The project is submitted to my lecturer, so the reasoning must be documented. |
| 15 | Read-only safety design | Claude | Three layers: (1) every query runs in a read-only transaction, so PostgreSQL rejects writes; (2) only a single `SELECT`/`WITH` statement is accepted and write keywords are blocked; (3) 15-second timeout and 200-row cap. | Accepted. | The task forbids modifying or deleting data. Several independent layers mean one mistake cannot cause a write. Tested: 7 different write attempts were blocked by layer 2, and the server refused a write in layer 1. (Layer 1 is now set per transaction instead of per session — see Issue 2.) |
| 16 | Glossary (semantic layer) | Me | — | Proposed by me: `GLOSSARY.md` with Term, Business meaning, SQL rule, Source table and Decision #; the dashboard and the agent's prompt must use exactly these definitions; linked from the README and kept up to date. | One shared vocabulary means the agent and the dashboard never disagree, and the lecturer can see exactly how each number is calculated. |
| 17 | Definition of "completed" (final) — supersedes #1 | Me | Completed = `completed_at IS NOT NULL` (4,911), from #1. After testing the dashboard I asked why the card showed 4,555; Claude showed the split of the 4,911 rows: 4,555 reached the final week (all certified, 100% progress, all with activity), 356 did not (0 reached the final week, 17.8% average progress, 120 with no activity, 0 certified, and every one has a completion date exactly 3 days before enrollment). | **Changed by me after data check → 4,555.** Completed = completion date present **and** final week reached (`last_week_reached >= n_weeks`). COMPLETED_PRIOR_CREDIT (#3) applies only to the 19 completed enrollments with a negative delta. | My principle stays the same: completion means all academic requirements were met. The data shows that `completed_at` alone is not reliable proof of that. The 356 extra rows contradict every learning signal, and their only evidence is a date that is systematically exactly 3 days before enrollment, which is a recording error. COMPLETED_PRIOR_CREDIT stays only for the 19 learners whose completion is confirmed by every other signal (final week reached, 100% progress, certified); it must not turn an invalid date into proof of completion. Completed and Certified remain different definitions that happen to give the same count (4,555) in this data. |
| 18 | Definition of "student" (final) — supersedes #4 | Claude | A data check found 40,000 users but only 37,529 distinct `user_id` in `enrollments`: 2,471 users signed up but never enrolled (no enrollment points to a missing user). Proposed: **Student = a user with at least one enrollment** (`COUNT(DISTINCT user_id)` in enrollments = 37,529), and a separate term **User** = anyone in `users` (40,000). One student can have many enrollments (2.52 on average, max 10). | Accepted. | We analyze learning behaviour, so only people who enrolled in at least one course count as students. Separating User, Student and Enrollment keeps sign-ups, learners and course enrollments from being mixed up. |
| 19 | Shared definitions | Claude | All definitions (date parsing, capped progress, completed, prior credit) live in one SQL block in `db.py` that is added to every query as a table called `enr`. | Accepted. | The dashboard and the agent always give the same numbers. |
| 20 | Database access from Python | Claude | The app connects with `DATABASE_URL` directly; the `course-db` MCP server is only used by Claude Code for exploration. | Accepted. | A Python app cannot use Claude's MCP connection. |
| 21 | Gemini model | Claude | `gemini-3.8-flash` (newest stable Flash model available on my key), overridable with `GEMINI_MODEL` in `.env`. | Accepted. | Fast and cheap enough for short analytical questions. It works for this homework, and the rate-limit message (#26) handles the free-tier limit. |
| 22 | Agent transparency | Claude | The dashboard shows every SQL query the agent ran, with row counts or errors. | Accepted. | Lets me check how each answer was produced. |
| 23 | Chart style | Claude | One blue colour, horizontal bars with count and % drop labels, a hover tooltip, and a table view. | Accepted. | One series needs no legend; the table makes the numbers accessible. |
| 24 | Package versions | Claude | Exact versions pinned in `requirements.txt`. | Accepted. | The project installs the same way for the lecturer. |
| 25 | Completion rate | Claude | Per enrollment: completed enrollments ÷ all enrollments × 100 (4.81%). Added to the glossary and the agent prompt. | Accepted. | The dashboard is built around enrollments, so the rate is per enrollment too. Writing it down keeps every answer consistent. |
| 26 | Rate-limit message | Claude | A Gemini 429 error shows a "wait about a minute" warning in the dashboard. | Accepted. | The free tier allows only a few requests per minute. |

## Issues & resolutions

| # | Issue | Cause | Resolution |
|---|---|---|---|
| 1 | `DATABASE_URL` missing from `.env`; the app could not connect. | The line was typed but not saved. | Saved the file and turned on Auto Save in VS Code. |
| 2 | After that, the connection failed: *"unsupported startup parameter in options: statement_timeout"*. | The database is on Neon and is reached through its connection pooler, which does not accept settings sent when the connection opens (the read-only mode and timeout were sent that way). | Claude moved both settings into each transaction: psycopg starts every transaction as `BEGIN READ ONLY`, followed by `SET LOCAL statement_timeout`. Verified: `transaction_read_only = on`, timeout 15 s, and the server refused a test write. |
| 3 | The agent's second test question failed with *429 RESOURCE_EXHAUSTED*. | Gemini free tier allows 5 requests per minute for `gemini-3.8-flash`, and one question can need several requests (one per SQL query plus the final answer). | The dashboard now shows a friendly "wait about a minute" message instead of an error. I kept `gemini-3.8-flash` (#21, #26). |

## Data quality findings

Problems found in the data itself. The data is never changed (read-only); the rules below decide how
each problem is handled in the metrics.

| # | Finding | Rows | How it is handled | Decision # |
|---|---|---|---|---|
| DQ1 | `completed_at` is present but there is no other evidence of completion: the completion date is exactly 3 days **before** enrollment, the final week was never reached (average progress 17.8%), none are certified, and 120 have no learning activity at all (funnel stages: 120 registered, 214 viewed, 22 explored). | 356 | Treated as a recording error. **Excluded from Completed** (`completion_status = 'NOT_COMPLETED'`). | #2, #17 |
| DQ2 | Completion date exactly 3 days before enrollment, but completion is confirmed by every other signal (final week reached, 100% progress, certified). | 19 | Counted as Completed, with `completion_status = 'COMPLETED_PRIOR_CREDIT'`. | #3, #17 |
| DQ3 | `progress_pct` above 100 (up to 104). | 277 | Capped at 100 for all progress metrics. | #5 |
| DQ4 | Dates stored as text in two formats (`YYYY-MM-DD` and `DD.MM.YYYY`). | 3,786 in the second format | Both formats parsed into real dates. | #6 |