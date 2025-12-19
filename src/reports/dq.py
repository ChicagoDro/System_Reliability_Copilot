# src/reports/dq.py
"""
Phase 1: DQ Failures.
Focus: Blocking issues only. No hotspots/trends.
"""

from __future__ import annotations
from typing import List, Dict, Any
from .base import ReportResult, connect, since_iso, row_to_dict

def dq_failures(db_path: str, *, days_back: int = 1) -> ReportResult:
    since = since_iso(days_back)
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
              dr.dq_result_id, dr.status, dr.observed_value, dr.run_id,
              rule.name AS rule_name, rule.severity,
              d.name AS dataset_name
            FROM dq_result dr
            JOIN dq_rule rule ON rule.rule_id = dr.rule_id
            LEFT JOIN dataset d ON d.dataset_id = dr.dataset_id
            WHERE dr.created_at >= ? AND dr.status IN ('fail','error')
            ORDER BY dr.created_at DESC
            LIMIT 50
            """,
            (since,),
        ).fetchall()

        failures = [row_to_dict(r) for r in rows]
        
        summary = f"DQ REPORT (Last {days_back} days)\n"
        if not failures:
            summary += "- No failures detected."
        else:
            summary += f"- Detected {len(failures)} failures.\n"
            for f in failures[:10]:
                summary += f"  * [{f['severity']}] {f['rule_name']} on {f['dataset_name']} (Run: {f['run_id']})\n"

        return ReportResult(
            ok=True,
            report_type="dq_failures",
            summary_text=summary,
            data={"failures": failures}
        )