# Glossary (semantic layer)

The single list of business terms and metrics used in this project. The dashboard (`app.py`) and the
agent's system prompt (`agent.py`) must use exactly these definitions. The SQL rules are implemented
once, in the shared `enr` table defined in `db.py` (`ENR_CTE`), which every query can use.

If a metric is added or changed, update this file, `db.py`, the agent prompt, and
[DECISIONS.md](DECISIONS.md) together.

Numbers are from the current data and are given for orientation only.

## Terms

| Term | Business meaning | Data definition (SQL rule) | Source table | Decision # |
|---|---|---|---|---|
| **User** | Anyone registered on the platform, whether or not they ever enrolled. 2,471 users signed up but never enrolled, so they are users but **not** students. | One row in `users`. Count: `COUNT(*) FROM users` → 40,000. | `users` | [#18](DECISIONS.md#decisions) |
| **Student** | A user with at least one enrollment — a person who actually started learning. One student can have many enrollments. Shown in the caption under **"Total enrollments"**. | `COUNT(DISTINCT user_id) FROM enr` → 37,529. | `enrollments` (every `user_id` exists in `users`) | [#18](DECISIONS.md#decisions) (supersedes #4) |
| **Enrollment** | One student taking one course. The unit for all progress and completion metrics. | One row in `enr`. Count: `COUNT(*) FROM enr` → 94,705 (on average 2.52 per student, max 10). | `enrollments` | — |
| **Enrollment date** | The day the student enrolled in the course. | `enrolled_date`: `enrolled_at` parsed from text; accepts `YYYY-MM-DD` and `DD.MM.YYYY`. | `enrollments` | [#6](DECISIONS.md#decisions) |
| **Completion date** | The recorded date the student met all academic requirements. On its own it is **not** proof of completion (356 rows have a date but no other evidence — see DQ1). | `completed_date`: `completed_at` parsed from text; same two formats. | `enrollments` | [#6, #17](DECISIONS.md#decisions) |
| **Completed** | The student met all academic requirements of the course (learning-based, not certificate-based): a completion date is recorded **and** the learner reached the final week. | `is_completed = (completed_date IS NOT NULL AND last_week_reached >= n_weeks)`. Count: `COUNT(*) FILTER (WHERE is_completed)` → 4,555. Shown on the **"Completed"** metric card. Rows with a `completed_at` but no final week (356) are **not** completed. | `enrollments` | [#17](DECISIONS.md#decisions) (supersedes #1); [#2, #3](DECISIONS.md#decisions) |
| **Completion status** | Whether an enrollment is completed, and whether its completion date looks anomalous. | `completion_status`: `'NOT_COMPLETED'` if not `is_completed` (includes the 356 invalid completion dates); `'COMPLETED_PRIOR_CREDIT'` if `is_completed` and `completed_date < enrolled_date` (19); otherwise `'COMPLETED'` (4,536). Prior credit applies **only** to completed enrollments and still counts as completed — a date before enrollment never makes an enrollment completed on its own. | `enrollments` | [#3, #17](DECISIONS.md#decisions) |
| **Certified** | The platform issued a certificate (administrative confirmation). A different definition from Completed, even though both give 4,555 in this data. | `funnel_state = 'certified'` (equivalently `is_certified = 1`) → 4,555. Shown as the last **"Certified"** funnel stage. | `enrollments` | [#9, #17](DECISIONS.md#decisions) |
| **Progress** | How far through the course one enrollment is, in %. | `progress_capped = LEAST(progress_pct, 100)`. Raw `progress_pct` can exceed 100 (tracking anomaly) and is not used for metrics. | `enrollments` | [#5](DECISIONS.md#decisions) |
| **Avg progress** | Average course progress across enrollments. | `AVG(progress_capped) FROM enr` → 21.1%. Shown on the **"Average progress"** metric card. | `enrollments` | [#5](DECISIONS.md#decisions) |
| **Completion rate** | Share of enrollments that are completed. | `100.0 * COUNT(*) FILTER (WHERE is_completed) / COUNT(*)` → 4.81% overall. Per enrollment, not per student. Uses the Completed definition above. | `enrollments` | [#25, #17](DECISIONS.md#decisions) |
| **Funnel stage** | The stage an enrollment is in right now. Order: Registered → Viewed → Explored → Certified. | `funnel_state` ∈ `registered` (enrolled, no activity), `viewed` (progress 1–49%), `explored` (50–99%), `certified` (final week reached, 100%). | `enrollments` | [#7](DECISIONS.md#decisions) |
| **Reached stage (cumulative)** | How many enrollments got at least as far as a stage. Used for the funnel chart. | Count of enrollments whose `funnel_state` is that stage **or any later stage**. Registered 94,705 → Viewed 61,619 → Explored 10,397 → Certified 4,555. | `enrollments` | [#8](DECISIONS.md#decisions) |
| **Drop % (funnel)** | Share of enrollments lost between one funnel stage and the next. | `100 * (1 − reached(stage) / reached(previous stage))` → −34.9%, −83.1%, −56.2%. | `enrollments` | [#8](DECISIONS.md#decisions) |

## User vs Student vs Enrollment

**Data check** (basis for decision #18)

| Check | Result |
|---|---|
| Rows in `users` (all distinct `user_id`) | 40,000 |
| Distinct `user_id` in `enrollments` | 37,529 |
| Users with no enrollment | 2,471 |
| Enrollments whose `user_id` is not in `users` | 0 |
| Enrollments with no `user_id` | 0 |
| Enrollments without a valid enrollment date | 0 |
| Enrollments per student | 2.52 on average, max 10 |

**The difference**

- A **User** is anyone in `users` (40,000). 2,471 signed up but never enrolled, so they are users but not students.
- A **Student** is a person (37,529). Count them with `COUNT(DISTINCT user_id)`.
- An **Enrollment** is one student in one course (94,705). One student can have up to 10 enrollments,
  so the number of students is always ≤ the number of enrollments. All progress and completion metrics
  are per enrollment, not per student.
