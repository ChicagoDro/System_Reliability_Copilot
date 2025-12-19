# src/reports/log_patterns.py
import pandas as pd
import streamlit as st
import plotly.express as px
from src.reports.base import ReportSpec, SelectionLike, Chip

def load_logs(db_path: str, filters: dict) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(db_path)
    # 1. Get Log Volume / Timeline
    query = """
    SELECT 
        l.log_id, l.severity_text, l.body, l.time,
        r.resource_id, r.name as resource_name, r.resource_type,
        p.display_name as platform
    FROM log_record l
    JOIN resource r ON l.resource_id = r.resource_id
    JOIN platform p ON r.platform_id = p.platform_id
    WHERE l.severity_text IN ('ERROR', 'FATAL', 'WARN')
    ORDER BY l.time DESC
    LIMIT 200
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def render_logs(df: pd.DataFrame, filters: dict):
    if df.empty:
        st.success("No critical logs found. System is quiet.")
        return

    # 1. Timeline Chart (Errors per Platform)
    st.caption("Error Volume by Platform")
    df["time"] = pd.to_datetime(df["time"])
    
    # Aggregate for chart
    chart_df = df.groupby(["platform", "severity_text"]).size().reset_index(name="count")
    
    fig = px.bar(
        chart_df, x="count", y="platform", color="severity_text",
        orientation='h', title="Log Volume (Last 24h)",
        color_discrete_map={"ERROR": "#EF553B", "FATAL": "#B22222", "WARN": "#FFA15A"}
    )
    st.plotly_chart(fig, use_container_width=True)

    # 2. Pattern Grouping (The "Signature" View)
    st.subheader("Top Log Signatures")
    # Naive grouping by first 50 chars to find "patterns"
    df["signature"] = df["body"].str.slice(0, 60) + "..."
    patterns = df.groupby(["signature", "resource_name", "severity_text"]).size().reset_index(name="occurrences")
    patterns = patterns.sort_values("occurrences", ascending=False).head(10)
    
    st.dataframe(
        patterns,
        column_config={
            "occurrences": st.column_config.ProgressColumn("Count", format="%d", min_value=0, max_value=int(patterns["occurrences"].max())),
        },
        use_container_width=True,
        hide_index=True
    )

def get_selections(df: pd.DataFrame, filters: dict) -> list[SelectionLike]:
    # Select unique signatures to investigate
    df["signature"] = df["body"].str.slice(0, 60) + "..."
    signatures = df.groupby(["signature", "resource_name", "resource_type"]).first().reset_index()
    
    selections = []
    for _, row in signatures.iterrows():
        # entity_id is technically the resource, but we label it with the error
        selections.append(SelectionLike(
            entity_type="log_pattern", 
            entity_id=row["resource_name"], # Anchor to the resource for the graph
            label=f"{row['severity_text']}: {row['signature']}"
        ))
    return selections

def get_chips(sel: SelectionLike, filters: dict) -> list[Chip]:
    return [
        Chip("log:explain", "🧐 Explain Error", 
             f"The resource {sel.entity_id} is throwing this error: '{sel.label}'. Explain what it means technically.", 
             group="Understand"),
        Chip("log:root_cause", "🔍 Find Root Cause", 
             f"Correlate the error '{sel.label}' on {sel.entity_id} with recent changes or runs. Is it a code bug or infrastructure?", 
             group="Diagnose"),
        Chip("log:filter", "🔇 Suggest Filter", 
             f"If this error '{sel.label}' is noise, how do I filter it out in DataDog/Splunk/CloudWatch?", 
             group="Optimize"),
    ]

REPORT = ReportSpec(
    key="log_patterns",
    name="Error Log Volume", # Matches the "Observability" pillar in your catalog
    description="Analysis of high-severity log patterns across platforms.",
    load_df=load_logs,
    render_viz=render_logs,
    build_selections=get_selections,
    build_action_chips=get_chips
)