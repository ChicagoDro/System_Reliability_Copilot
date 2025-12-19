# src/reports/recent_incidents.py
import pandas as pd
import streamlit as st
import plotly.express as px
from src.reports.base import ReportSpec, SelectionLike, Chip

def load_incidents(db_path: str, filters: dict) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(db_path)
    query = """
    SELECT 
        incident_id, title, severity, status, 
        env_id, summary, opened_at, closed_at
    FROM incident
    ORDER BY opened_at DESC
    LIMIT 50
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def render_incidents(df: pd.DataFrame, filters: dict):
    if df.empty:
        st.info("No recent incidents found.")
        return

    # Metrics Row
    c1, c2, c3 = st.columns(3)
    c1.metric("Open Incidents", len(df[df['status'] != 'RESOLVED']))
    c2.metric("Sev-1 (High)", len(df[df['severity'] == 'HIGH']))
    c3.metric("Recent Total", len(df))

    # Simple Timeline Chart
    if not df.empty:
        fig = px.scatter(
            df, x="opened_at", y="severity", 
            color="status", hover_data=["title"],
            title="Incident Timeline"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df[["severity", "status", "title", "opened_at", "env_id"]],
        use_container_width=True,
        hide_index=True
    )

def get_selections(df: pd.DataFrame, filters: dict) -> list[SelectionLike]:
    selections = []
    for _, row in df.head(5).iterrows():
        selections.append(SelectionLike(
            entity_type="incident",
            entity_id=row["incident_id"],
            label=f"{row['severity']} - {row['title']}"
        ))
    return selections

def get_chips(sel: SelectionLike, filters: dict) -> list[Chip]:
    return [
        Chip("inc:summary", "📝 Draft Post-Mortem", 
             f"Draft a post-mortem summary for incident {sel.entity_id}. Include timeline, root cause analysis (if known), and future prevention steps.", 
             group="Diagnose"),
        Chip("inc:impact", "💥 Assess Impact", 
             f"What was the business impact of incident {sel.entity_id}? Check connected runs and resources.", 
             group="Understand"),
    ]

REPORT = ReportSpec(
    key="recent_incidents",
    name="Recent Incidents",
    description="Overview of recent system outages and alerts.",
    load_df=load_incidents,
    render_viz=render_incidents,
    build_selections=get_selections,
    build_action_chips=get_chips
)