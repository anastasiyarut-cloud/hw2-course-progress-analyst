"""Streamlit dashboard: course progress KPIs, learning funnel, and a question box for the agent."""

import os

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.genai import errors as genai_errors

from agent import ask
from db import run_select

load_dotenv()

st.set_page_config(page_title="Course Progress Analyst", layout="wide")
st.title("Course Progress Analyst")

missing = [k for k in ("DATABASE_URL", "GEMINI_API_KEY") if not os.getenv(k)]
if missing:
    st.error(f"Missing in .env: {', '.join(missing)}. See .env.example.")
    st.stop()

FUNNEL_ORDER = ["registered", "viewed", "explored", "certified"]
BAR_COLOR = "#2a78d6"


@st.cache_data(ttl=600, show_spinner="Loading metrics...")
def load_kpis() -> pd.Series:
    df, _ = run_select("""
        SELECT COUNT(*)                                                    AS enrollments,
               COUNT(DISTINCT user_id)                                     AS students,
               AVG(progress_capped)                                        AS avg_progress,
               COUNT(*) FILTER (WHERE is_completed)                        AS completed,
               COUNT(*) FILTER (WHERE completion_status = 'COMPLETED_PRIOR_CREDIT') AS prior_credit
        FROM enr
    """)
    return df.iloc[0]


@st.cache_data(ttl=600, show_spinner="Loading funnel...")
def load_funnel() -> pd.DataFrame:
    df, _ = run_select("SELECT funnel_state, COUNT(*) AS n FROM enr GROUP BY funnel_state")
    df = df.set_index("funnel_state").reindex(FUNNEL_ORDER, fill_value=0).reset_index()
    # funnel_state is the CURRENT stage, so "reached at least" = this stage + all later ones.
    df["reached"] = df["n"][::-1].cumsum()[::-1].astype(int)
    df["stage"] = df["funnel_state"].str.capitalize()
    df["drop_pct"] = (1 - df["reached"] / df["reached"].shift(1)) * 100
    df["label"] = df.apply(
        lambda r: f"{r.reached:,}" + ("" if pd.isna(r.drop_pct) else f"  (−{r.drop_pct:.1f}%)"), axis=1
    )
    return df


kpis = load_kpis()
col1, col2, col3 = st.columns(3)
col1.metric("Total enrollments", f"{int(kpis.enrollments):,}")
col1.caption(f"From {int(kpis.students):,} students (users with at least one enrollment)")
col2.metric("Average progress", f"{float(kpis.avg_progress):.1f}%")
col2.caption("Progress capped at 100% per enrollment")
col3.metric("Completed", f"{int(kpis.completed):,}")
col3.caption(
    f"Completion date present and final week reached. Includes {int(kpis.prior_credit)} "
    "COMPLETED_PRIOR_CREDIT. “Completed” and “Certified” (funnel) are different definitions "
    "that happen to give the same count in this data."
)

st.subheader("Learning funnel")
st.caption("Enrollments that reached at least each stage, with the drop from the previous stage.")
funnel = load_funnel()
base = alt.Chart(funnel).encode(
    y=alt.Y("stage:N", sort=[s.capitalize() for s in FUNNEL_ORDER], title=None),
    x=alt.X("reached:Q", title="Enrollments", axis=alt.Axis(format=",d")),
    tooltip=[
        alt.Tooltip("stage:N", title="Stage"),
        alt.Tooltip("reached:Q", title="Reached at least", format=",d"),
        alt.Tooltip("drop_pct:Q", title="Drop from previous (%)", format=".1f"),
    ],
)
bars = base.mark_bar(color=BAR_COLOR, cornerRadiusEnd=4, size=28)
labels = base.mark_text(align="left", dx=6).encode(text="label:N")
st.altair_chart((bars + labels).properties(height=220), width="stretch")
with st.expander("Funnel as a table"):
    st.dataframe(
        funnel[["stage", "reached", "drop_pct"]].rename(
            columns={"stage": "Stage", "reached": "Reached at least", "drop_pct": "Drop from previous (%)"}
        ),
        hide_index=True,
        column_config={"Drop from previous (%)": st.column_config.NumberColumn(format="%.1f")},
    )

st.subheader("Ask the analyst")
with st.form("ask"):
    question = st.text_input("Your question", placeholder="e.g. Which course level has the highest completion rate?")
    submitted = st.form_submit_button("Ask")

if submitted and question.strip():
    with st.spinner("Analyzing..."):
        try:
            answer = ask(question.strip())
        except genai_errors.ClientError as exc:
            if exc.code == 429:
                st.warning("Gemini's request limit was reached (free tier: a few requests per minute). "
                           "Wait about a minute and ask again.")
            else:
                st.error(f"Gemini error: {exc}")
        except Exception as exc:
            st.error(f"The agent failed: {exc}")
        else:
            st.markdown(answer.text)
            if answer.queries:
                with st.expander(f"SQL used ({len(answer.queries)} quer{'y' if len(answer.queries) == 1 else 'ies'})"):
                    for q in answer.queries:
                        st.code(q.sql, language="sql")
                        st.caption(f"Error: {q.error}" if q.error else f"{q.rows} row(s) returned")
