#**`src/reports/run_history.py`**
#*Why:* Shows a timeline of ALL runs (Airflow, K8s, dbt, Databricks) in one view.

import pandas as pd
import streamlit as st
import plotly.express as px
from src.reports.base import ReportSpec, SelectionLike, Chip

def load_runs(db_path: str, filters: dict) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(db_path)
    # Get all runs with their platform info
    query = """
    SELECT 
        r.run_id, r.resource_id, r.status, r.started_at, r.ended_at, r.message,
        res.name as resource_name, res.resource_type,
        p.display_name as platform
    FROM run r
    JOIN resource res ON r.resource_id = res.resource_id
    JOIN platform p ON res.platform_id = p.platform_id
    ORDER BY r.started_at DESC
    LIMIT 100
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def render_runs(df: pd.DataFrame, filters: dict):
    if df.empty:
        st.info("No run history found.")
        return
    
    # 1. Timeline Chart
    st.caption("Execution Timeline (All Platforms)")
    # Ensure dates are datetime for Plotly
    df["start"] = pd.to_datetime(df["started_at"])
    df["end"] = pd.to_datetime(df["ended_at"]).fillna(pd.Timestamp.now())
    
    fig = px.timeline(
        df, x_start="start", x_end="end", y="resource_name",
        color="status", hover_data=["message", "platform"],
        color_discrete_map={"SUCCESS": "#00CC96", "FAILED": "#EF553B", "running": "#636EFA"}
    )
    fig.update_yaxes(categoryorder="total ascending")
    st.plotly_chart(fig, use_container_width=True)

    # 2. Detailed Table
    st.dataframe(
        df[["platform", "resource_name", "status", "message", "started_at"]],
        use_container_width=True,
        hide_index=True
    )

def get_selections(df: pd.DataFrame, filters: dict) -> list[SelectionLike]:
    return [
        SelectionLike(entity_type="run", entity_id=r["run_id"], label=f"{r['platform']} - {r['resource_name']}")
        for _, r in df.iterrows()
    ]

def get_chips(sel: SelectionLike, filters: dict) -> list[Chip]:
    return [
        Chip("run:logs", "📄 Analyze Logs", f"Fetch the logs for run {sel.entity_id} and explain why it failed.", group="Diagnose"),
        Chip("run:fix", "🔧 Suggest Fix", f"Based on the failure message, what is the runbook procedure to fix run {sel.entity_id}?", group="Optimize"),
    ]

REPORT = ReportSpec(
    key="run_history",
    name="Run History",
    description="Cross-platform execution timeline (Airflow, dbt, Databricks, K8s).",
    load_df=load_runs,
    render_viz=render_runs,
    build_selections=get_selections,
    build_action_chips=get_chips
)
