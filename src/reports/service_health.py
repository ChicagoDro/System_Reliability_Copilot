# src/reports/service_health.py
import pandas as pd
import streamlit as st
import plotly.express as px
from src.reports.base import ReportSpec, SelectionLike, Chip

def load_service_data(db_path: str, filters: dict) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(db_path)
    
    # Fetch metrics specifically for Services/Nodes (Infra view)
    # We look for 'latency', 'requests', 'cpu', 'memory'
    query = """
    SELECT 
        m.time, m.metric_name, m.value_number, m.unit,
        r.resource_id, r.name as resource_name, r.resource_type, 
        p.display_name as platform
    FROM metric_point m
    JOIN resource r ON m.resource_id = r.resource_id
    JOIN platform p ON r.platform_id = p.platform_id
    WHERE r.resource_type IN ('service', 'node', 'pod', 'database')
    ORDER BY m.time ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty: return df
    
    df["time"] = pd.to_datetime(df["time"])
    return df

def render_service_health(df: pd.DataFrame, filters: dict):
    if df.empty:
        st.info("No infrastructure metrics found (Golden Signals).")
        return

    # 1. Latency Heatmap (The "SRE Dashboard" View)
    st.caption("Service Latency (P95) & Health")
    
    # Filter for latency metrics for the main chart
    latency_df = df[df["metric_name"].str.contains("lat", case=False)]
    
    if not latency_df.empty:
        fig = px.line(
            latency_df, x="time", y="value_number", color="resource_name",
            markers=True, title="P95 Latency Over Time (ms)",
            labels={"value_number": "Latency (ms)"}
        )
        # Add "Danger Zone" line
        fig.add_hline(y=2000, line_dash="dash", line_color="red", annotation_text="SLO Breach (2s)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No latency metrics detected.")

    # 2. Infra Health Cards
    latest_time = df["time"].max()
    recent = df[df["time"] >= (latest_time - pd.Timedelta(hours=1))]
    
    st.subheader("Current Infrastructure State")
    cols = st.columns(3)
    
    # distinct resources
    resources = recent["resource_name"].unique()
    for i, res in enumerate(resources[:6]): # Show top 6
        res_metrics = recent[recent["resource_name"] == res]
        # Try to find a metric to show
        val = res_metrics.iloc[-1]["value_number"]
        unit = res_metrics.iloc[-1]["unit"]
        metric = res_metrics.iloc[-1]["metric_name"]
        
        with cols[i % 3]:
            st.metric(label=res, value=f"{val:.0f} {unit}", delta=metric)

def get_selections(df: pd.DataFrame, filters: dict) -> list[SelectionLike]:
    # Select services that have metrics
    resources = df[["resource_id", "resource_name", "resource_type"]].drop_duplicates()
    return [
        SelectionLike(
            entity_type=row["resource_type"], 
            entity_id=row["resource_id"], 
            label=f"INFRA: {row['resource_name']}"
        ) 
        for _, row in resources.iterrows()
    ]

def get_chips(sel: SelectionLike, filters: dict) -> list[Chip]:
    return [
        Chip("infra:scale", "⚖️ Check Scaling", 
             f"Check the autoscaling group settings for {sel.entity_id}. Is it capped at max replicas? Is CPU saturation high?", 
             group="Optimize"),
        Chip("infra:logs", "📜 Traffic Logs", 
             f"Fetch the ingress/access logs for {sel.entity_id} during the latency spike. Are we seeing 500 errors or a DDoS pattern?", 
             group="Diagnose"),
        Chip("infra:rollback", "🔙 Rollback Plan", 
             f"If {sel.entity_id} was recently deployed, draft the command to rollback to the previous stable version immediately.", 
             group="Fix"),
    ]

REPORT = ReportSpec(
    key="service_health",
    name="Service Health (Golden Signals)", # SRE terminology
    description="Monitor Latency, Traffic, Errors, and Saturation for services.",
    load_df=load_service_data,
    render_viz=render_service_health,
    build_selections=get_selections,
    build_action_chips=get_chips
)