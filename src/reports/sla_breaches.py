# src/reports/sla_breaches.py
import pandas as pd
import streamlit as st
import plotly.express as px
import json
from src.reports.base import ReportSpec, SelectionLike, Chip

def load_sla_data(db_path: str, filters: dict) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(db_path)
    
    # 1. Fetch Run Durations + JSON Attributes
    query = """
    SELECT 
        r.run_id, r.resource_id, r.status, r.started_at, r.ended_at,
        res.name as resource_name, res.resource_type, res.platform_id,
        res.attributes_json
    FROM run r
    JOIN resource res ON r.resource_id = res.resource_id
    WHERE r.started_at IS NOT NULL 
      AND r.ended_at IS NOT NULL
    ORDER BY r.started_at DESC
    LIMIT 500
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        return df

    # 2. Process Durations
    df["start"] = pd.to_datetime(df["started_at"])
    df["end"] = pd.to_datetime(df["ended_at"])
    df["duration_mins"] = (df["end"] - df["start"]).dt.total_seconds() / 60.0
    
    # 3. Parse SLA from JSON (New Logic)
    def get_sla(row):
        try:
            attrs = json.loads(row["attributes_json"] or "{}")
            return float(attrs.get("sla_runtime_mins", 0))
        except:
            return 0.0

    df["sla_limit"] = df.apply(get_sla, axis=1)

    # 4. Calculate Average Baseline (Fallback)
    stats = df.groupby("resource_name")["duration_mins"].mean().reset_index(name="avg_duration")
    df = df.merge(stats, on="resource_name")
    
    # 5. Flag Breaches (Smart Logic)
    # If SLA is defined (>0), use it. Else use 1.5x Average.
    def check_breach(row):
        if row["sla_limit"] > 0:
            return row["duration_mins"] > row["sla_limit"]
        return row["duration_mins"] > (row["avg_duration"] * 1.5)

    df["is_slow"] = df.apply(check_breach, axis=1)
    
    # Label the breach reason for the UI
    df["breach_type"] = df.apply(
        lambda r: f"Exceeded SLA ({int(r['sla_limit'])}m)" if r["sla_limit"] > 0 else "Anomaly (>1.5x avg)", 
        axis=1
    )
    
    return df

def render_sla(df: pd.DataFrame, filters: dict):
    if df.empty:
        st.info("No run history available for SLA analysis.")
        return

    # 1. KPI Cards
    slow_runs = df[df["is_slow"]]
    col1, col2 = st.columns(2)
    col1.metric("Avg Run Duration", f"{df['duration_mins'].mean():.1f} min")
    col2.metric("SLA Breaches", len(slow_runs), delta_color="inverse")

    # 2. Scatter Plot
    st.caption("Performance Trends (Duration vs Time)")
    fig = px.scatter(
        df, x="start", y="duration_mins", 
        color="resource_name", 
        symbol="is_slow", 
        size="duration_mins",
        hover_data=["run_id", "breach_type"],
        title="Job Duration & SLA Status"
    )
    st.plotly_chart(fig, use_container_width=True)

    # 3. The "Breach List"
    if not slow_runs.empty:
        st.subheader("⚠️ Breach Details")
        display_cols = ["resource_name", "duration_mins", "sla_limit", "avg_duration", "breach_type"]
        st.dataframe(
            slow_runs[display_cols].sort_values("duration_mins", ascending=False),
            column_config={
                "duration_mins": st.column_config.NumberColumn("Actual (m)", format="%.1f"),
                "sla_limit": st.column_config.NumberColumn("SLA Target (m)", format="%.1f"),
                "avg_duration": st.column_config.NumberColumn("Avg (m)", format="%.1f"),
            },
            use_container_width=True,
            hide_index=True
        )

def get_selections(df: pd.DataFrame, filters: dict) -> list[SelectionLike]:
    slow_runs = df[df["is_slow"]].head(20)
    return [
        SelectionLike(
            entity_type="run", 
            entity_id=row["run_id"], 
            label=f"BREACH: {row['resource_name']} ({row['duration_mins']:.0f}m)"
        ) 
        for _, row in slow_runs.iterrows()
    ]

def get_chips(sel: SelectionLike, filters: dict) -> list[Chip]:
    return [
        Chip("sla:why", "🐢 Analyze Delay", 
             f"Run {sel.entity_id} breached its performance target. Was it queueing, data volume, or code efficiency?", 
             group="Diagnose"),
        Chip("sla:tune", "⚡ Tune Performance", 
             f"Suggest configuration changes to bring {sel.entity_id} back within its SLA.", 
             group="Optimize"),
    ]

REPORT = ReportSpec(
    key="sla_breaches",
    name="SLA Breaches", 
    description="Identify runs that exceeded their explicit SLA or historical baseline.",
    load_df=load_sla_data,
    render_viz=render_sla,
    build_selections=get_selections,
    build_action_chips=get_chips
)