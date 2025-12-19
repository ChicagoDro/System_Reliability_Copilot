# src/reports/incidents.py
"""
Phase 1: Incident report (Firefighter Edition).

Focus:
- Run Status & Timing
- Error Logs (Trace)
- DQ Failures (Root Cause)
"""

from __future__ import annotations
from typing import List
from .base import ReportResult, connect, parse_json, row_to_dict, fmt_platform_env

def incident_report_for_run(db_path: str, run_id: str, *, log_limit: int = 20) -> ReportResult:
    with connect(db_path) as conn:
        # 1. Fetch Run & Resource Context
        r = conn.execute(
            """
            SELECT
              run.*,
              res.name AS resource_name,
              res.resource_type,
              res.namespace,
              p.display_name AS platform_name,
              e.name AS env_name
            FROM run
            JOIN resource res ON res.resource_id = run.resource_id
            LEFT JOIN platform p ON p.platform_id = run.platform_id
            LEFT JOIN environment e ON e.env_id = run.env_id
            WHERE run.run_id = ?
            """,
            (run_id,),
        ).fetchone()

        if not r:
            return ReportResult(False, "incident_report", f"Run {run_id} not found.", {"run_id": run_id})

        # 2. Fetch Error Logs (The "Smoke")
        logs = conn.execute(
            """
            SELECT time, severity_text, body
            FROM log_record
            WHERE run_id = ? AND severity_text IN ('ERROR', 'FATAL', 'WARN')
            ORDER BY time DESC
            LIMIT ?
            """,
            (run_id, log_limit),
        ).fetchall()

        # 3. Fetch DQ Failures (The "Fire")
        dq = conn.execute(
            """
            SELECT
              dr.status, dr.observed_value, dr.expected_value,
              rule.name AS rule_name, rule.severity,
              d.name AS dataset_name
            FROM dq_result dr
            JOIN dq_rule rule ON rule.rule_id = dr.rule_id
            LEFT JOIN dataset d ON d.dataset_id = dr.dataset_id
            WHERE dr.run_id = ? AND dr.status IN ('fail','error')
            ORDER BY dr.created_at DESC
            LIMIT 20
            """,
            (run_id,),
        ).fetchall()

        # Build Summary
        lines: List[str] = []
        lines.append(f"INCIDENT REPORT FOR RUN: {run_id}")
        lines.append(f"- Resource: {r['resource_name']} ({r['resource_type']})")
        lines.append(f"- Status: {r['status']} | Ended: {r['ended_at']}")
        lines.append(f"- Message: {r['message']}")
        
        if dq:
            lines.append(f"\nCRITICAL: {len(dq)} Data Quality Failure(s) Detected")
            for x in dq:
                lines.append(f"  * Rule '{x['rule_name']}' failed on '{x['dataset_name']}': Observed {x['observed_value']} (Expect {x['expected_value']})")
        
        if logs:
            lines.append(f"\nLOG EVIDENCE ({len(logs)} lines):")
            for l in logs:
                lines.append(f"  * [{l['time']}] {l['severity_text']}: {l['body']}")

        return ReportResult(
            ok=True,
            report_type="incident_report",
            summary_text="\n".join(lines),
            data={
                "run": row_to_dict(r),
                "logs": [row_to_dict(x) for x in logs],
                "dq_failures": [row_to_dict(x) for x in dq]
            },
        )