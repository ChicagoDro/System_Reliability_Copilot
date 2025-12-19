# src/reports/sla.py
"""
SLA reports for the new Reliability Copilot schema.

Two sources of truth:
1) Explicit: run.attributes_json contains {"sla_breached": true}
2) Computed: compare run duration to sla_policy.max_duration_seconds for that resource

This is intentionally simple (works great for demo + lite).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import ReportResult, connect, parse_json, row_to_dict, since_iso, fmt_platform_env


def _try_duration_seconds(started_at: Optional[str], ended_at: Optional[str]) -> Optional[float]:
    if not started_at or not ended_at:
        return None
    try:
        s = datetime.fromisoformat(str(started_at))
        e = datetime.fromisoformat(str(ended_at))
        return (e - s).total_seconds()
    except Exception:
        return None


def sla_breaches(db_path: str, *, days_back: int = 7, limit: int = 50) -> ReportResult:
    since = since_iso(days_back)

    with connect(db_path) as conn:
        policies = conn.execute(
            """
            SELECT sla_id, resource_id, max_duration_seconds, max_cost_usd, availability_target
            FROM sla_policy
            """
        ).fetchall()
        pol_map = {p["resource_id"]: row_to_dict(p) for p in policies}

        runs = conn.execute(
            """
            SELECT
              r.*,
              res.name AS resource_name,
              res.resource_type AS resource_type,
              p.display_name AS platform_name,
              e.name AS env_name
            FROM run r
            JOIN resource res ON res.resource_id = r.resource_id
            LEFT JOIN platform p ON p.platform_id = r.platform_id
            LEFT JOIN environment e ON e.env_id = r.env_id
            WHERE COALESCE(r.started_at, r.created_at) >= ?
            ORDER BY COALESCE(r.started_at, r.created_at) DESC
            LIMIT ?
            """,
            (since, limit * 15),
        ).fetchall()

        breaches: List[Dict[str, Any]] = []
        for r in runs:
            attrs = parse_json(r["attributes_json"])
            explicit = attrs.get("sla_breached") is True

            dur = _try_duration_seconds(r["started_at"], r["ended_at"])
            pol = pol_map.get(r["resource_id"])
            computed = False
            if pol and dur is not None and pol.get("max_duration_seconds") is not None:
                computed = dur > float(pol["max_duration_seconds"])

            if explicit or computed:
                breaches.append(
                    {
                        "run_id": r["run_id"],
                        "resource_id": r["resource_id"],
                        "resource_name": r["resource_name"],
                        "resource_type": r["resource_type"],
                        "platform_env": fmt_platform_env(r["platform_name"], r["platform_id"], r["env_name"], r["env_id"]),
                        "status": r["status"],
                        "started_at": r["started_at"],
                        "ended_at": r["ended_at"],
                        "duration_seconds": dur,
                        "policy": pol,
                        "reason": "explicit_sla_breached" if explicit else "duration_exceeded_policy",
                        "run_attrs": attrs,
                    }
                )
            if len(breaches) >= limit:
                break

        lines: List[str] = []
        lines.append("SLA BREACH REPORT")
        lines.append(f"- Window: last {days_back} days")
        lines.append(f"- Breaches: {len(breaches)}")
        for b in breaches[:12]:
            lines.append(
                f"- {b['resource_name']} ({b['platform_env']}): run={b['run_id']} "
                f"reason={b['reason']} duration_s={b['duration_seconds']}"
            )

        return ReportResult(
            ok=True,
            report_type="sla_breaches",
            summary_text="\n".join(lines),
            data={"breaches": breaches},
        )
