#**`src/reports/metric_anomalies.py`**
#*Why:* Unlocks the Snowflake "Data Loss" scenario by visualizing the drop to 0 rows.

import pandas as pd
import streamlit as st
import plotly.express as px
from src.reports.base import ReportSpec, SelectionLike, Chip

def load_metrics(db_path: str, filters: dict) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(db_path)
    # Fetch metrics for resources
    query = """
    SELECT 
        m.metric_name, m.value_number, m.time,
        r.resource_id, r.name as resource_name
    FROM metric_point m
    JOIN resource r ON m.resource_id = r.resource_id
    ORDER BY m.time ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def render_metrics(df: pd.DataFrame, filters: dict):
    if df.empty:
        st.info("No metric data found.")
        return

    st.caption("Metric Trends")
    # Facet chart by resource/metric
    fig = px.line(
        df, x="time", y="value_number", color="resource_name",
        markers=True, title="Row Counts / Gauge Metrics"
    )
    st.plotly_chart(fig, use_container_width=True)

    # Highlight anomalies (Zero values)
    zeros = df[df["value_number"] == 0]
    if not zeros.empty:
        st.error(f"⚠️ DETECTED {len(zeros)} ANOMALIES (Value = 0)")
        st.dataframe(zeros, use_container_width=True)

def get_selections(df: pd.DataFrame, filters: dict) -> list[SelectionLike]:
    # Select unique resources that have metrics
    resources = df[["resource_id", "resource_name"]].drop_duplicates()
    return [
        SelectionLike(entity_type="resource", entity_id=r["resource_id"], label=f"Metric: {r['resource_name']}")
        for _, r in resources.iterrows()
    ]

def get_chips(sel: SelectionLike, filters: dict) -> list[Chip]:
    return [
        Chip("met:why", "📉 Why the drop?", f"Analyze the metric drop for {sel.entity_id}. Is there an associated incident?", group="Diagnose"),
    ]

REPORT = ReportSpec(
    key="metric_anomalies",
    name="Metric Anomalies",
    description="Time-series view of system metrics (Row Counts, Latency).",
    load_df=load_metrics,
    render_viz=render_metrics,
    build_selections=get_selections,
    build_action_chips=get_chips
)
