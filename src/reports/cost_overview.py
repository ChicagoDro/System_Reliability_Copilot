# src/reports/cost_overview.py
import pandas as pd
import streamlit as st
import plotly.express as px
from src.reports.base import ReportSpec, SelectionLike, Chip

def load_cost_data(db_path: str, filters: dict) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(db_path)
    
    # Fetch 'daily_cost' metrics joined with resource metadata
    query = """
    SELECT 
        m.time, m.value_number as cost,
        r.resource_id, r.name as resource_name, r.resource_type, 
        p.display_name as platform
    FROM metric_point m
    JOIN resource r ON m.resource_id = r.resource_id
    JOIN platform p ON r.platform_id = p.platform_id
    WHERE m.metric_name = 'daily_cost'
    ORDER BY m.time ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty: return df

    df["date"] = pd.to_datetime(df["time"]).dt.date
    return df

def render_cost(df: pd.DataFrame, filters: dict):
    if df.empty:
        st.info("No cost data available.")
        return

    # 1. KPI Cards (Last 7 Days vs Previous 7 Days)
    last_date = df["date"].max()
    last_7 = df[df["date"] >= (last_date - pd.Timedelta(days=7))]
    prev_7 = df[(df["date"] < (last_date - pd.Timedelta(days=7))) & 
                (df["date"] >= (last_date - pd.Timedelta(days=14)))]
    
    total_spend = last_7["cost"].sum()
    prev_spend = prev_7["cost"].sum()
    delta = ((total_spend - prev_spend) / prev_spend * 100) if prev_spend > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("7-Day Spend", f"${total_spend:,.2f}", f"{delta:+.1f}%")
    col2.metric("Top Spender", last_7.groupby("resource_name")["cost"].sum().idxmax())
    col3.metric("Data Points", len(df))

    # 2. Stacked Area Chart (Spend by Platform/Resource)
    st.subheader("Daily Spend Trend")
    daily_agg = df.groupby(["date", "resource_name", "platform"])["cost"].sum().reset_index()
    
    fig = px.area(
        daily_agg, x="date", y="cost", color="resource_name",
        line_group="platform", title="Daily Cost by Resource",
        labels={"cost": "Cost ($)", "date": "Date"}
    )
    st.plotly_chart(fig, use_container_width=True)

    # 3. Top Spenders Table
    st.subheader("Resource Breakdown (Last 30 Days)")
    summary = df.groupby(["resource_name", "platform", "resource_type"])["cost"].agg(["sum", "mean", "max"]).reset_index()
    summary = summary.rename(columns={"sum": "total_cost", "mean": "avg_daily", "max": "peak_daily"})
    
    st.dataframe(
        summary.sort_values("total_cost", ascending=False),
        column_config={
            "total_cost": st.column_config.NumberColumn("Total ($)", format="$%.2f"),
            "avg_daily": st.column_config.NumberColumn("Avg ($)", format="$%.2f"),
            "peak_daily": st.column_config.NumberColumn("Peak ($)", format="$%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )

def get_selections(df: pd.DataFrame, filters: dict) -> list[SelectionLike]:
    # Unique resources found in the cost report
    resources = df[["resource_id", "resource_name", "platform"]].drop_duplicates()
    return [
        SelectionLike(
            entity_type="resource", 
            entity_id=row["resource_id"], 
            label=f"COST: {row['resource_name']} ({row['platform']})"
        ) 
        for _, row in resources.iterrows()
    ]

def get_chips(sel: SelectionLike, filters: dict) -> list[Chip]:
    return [
        Chip("cost:analyze", "💰 Analyze Spend", 
             f"Analyze the cost trend for {sel.entity_id}. Is the increase linear (data growth) or sudden (inefficiency)?", 
             group="Diagnose"),
        Chip("cost:optimize", "📉 Reduce Bill", 
             f"Consult the 'Databricks Cost Optimization Runbook' to find ways to lower the cost of {sel.entity_id}. Suggest spot instances or query tuning.", 
             group="Optimize"),
    ]

REPORT = ReportSpec(
    key="cost_overview",
    name="Cloud Cost Overview",
    description="Track daily spend, identify spikes, and find efficiency opportunities.",
    load_df=load_cost_data,
    render_viz=render_cost,
    build_selections=get_selections,
    build_action_chips=get_chips
)