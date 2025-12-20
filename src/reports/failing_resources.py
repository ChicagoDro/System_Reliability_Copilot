# src/reports/failing_resources.py
import pandas as pd
import streamlit as st
from src.reports.base import ReportSpec, SelectionLike, Chip

def load_failing(db_path: str, filters: dict) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(db_path)
    query = """
    SELECT 
        r.resource_id, r.name, r.resource_type, r.platform_id,
        COUNT(run.run_id) as failure_count,
        MAX(run.ended_at) as last_failure,
        MAX(run.run_id) as last_failed_run_id
    FROM resource r
    JOIN run ON r.resource_id = run.resource_id
    WHERE run.status != 'SUCCESS'
    GROUP BY r.resource_id
    ORDER BY failure_count DESC
    LIMIT 20
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def render_failing(df: pd.DataFrame, filters: dict):
    if df.empty:
        st.success("No failing resources found! System is healthy.")
        return

    st.warning(f"Found {len(df)} resources with recent failures.")
    
    max_fails = int(df["failure_count"].max()) if not df.empty else 10

    st.dataframe(
        df,
        column_config={
            "failure_count": st.column_config.ProgressColumn(
                "Failures", 
                min_value=0, 
                max_value=max_fails,
                format="%d"
            ),
            "last_failure": st.column_config.DatetimeColumn(
                "Last Failure",
                format="D MMM, HH:mm"
            )
        },
        use_container_width=True,
        hide_index=True
    )

def get_selections(df: pd.DataFrame, filters: dict) -> list[SelectionLike]:
    selections = []
    for _, row in df.iterrows():
        selections.append(SelectionLike(
            entity_type="resource",
            entity_id=row["resource_id"],
            label=f"{row['name']} ({row['failure_count']} fails)"
        ))
    return selections

def get_chips(sel: SelectionLike, filters: dict) -> list[Chip]:
    return [
        Chip(
            "res:deep_dive", 
            "🔬 Deep Dive (9 steps)", 
            "INVESTIGATE:run_failure",
            investigation_plan="run_failure",
            group="Diagnose"
        ),
        Chip(
            "res:debug", 
            "🐞 Debug Last Run", 
            f"Analyze the logs of the last failed run for resource {sel.entity_id}. What is the error message?", 
            group="Diagnose"
        ),
        Chip(
            "res:owner", 
            "👤 Find Owner", 
            f"Who owns resource {sel.entity_id}? Check metadata and suggest who to page.", 
            group="Understand"
        ),
    ]

REPORT = ReportSpec(
    key="failing_resources",
    name="Failing Resources",
    description="Top resources generating errors or failing runs.",
    load_df=load_failing,
    render_viz=render_failing,
    build_selections=get_selections,
    build_action_chips=get_chips
)