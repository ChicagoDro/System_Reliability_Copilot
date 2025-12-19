# src/reports/cost.py
"""
Cost reports for the new Reliability Copilot schema.

Right now we implement:
- cost_anomalies: simple spike detection per resource (great for demos + lite)

Later (once you like the dimensions), we can add:
- cost_pareto_by_resource (top 20 cost drivers)
- cost_by_platform_env
- cost_by_compute_config (if you normalize compute config tags)

Tables used:
- cost_record, resource, platform, environment, run
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Dict, List, Optional

from .base import ReportResult, connect, since_iso, parse_json, safe_json, row_to_dict


def cost_anomalies(db_path: str, *, days_back: int = 14, limit: int = 50, spike_ratio: float = 2.0) -> ReportResult:
    """
    For each resource_id:
      - take latest cost record in window
      - compare to median of previous up to 5 records
      - flag if latest >= spike_ratio * median

    This is intentionally simple and deterministic.
    """
    since = since_iso(days_back)

    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
              c.resource_id, c.run_id, c.platform_id, c.env_id,
              c.time, c.cost_usd, c.currency, c.attributes_json,
              res.name AS resource_name,
              res.resource_type AS resource_type,
              p.display_name AS platform_name,
              e.name AS env_name
            FROM cost_record c
            LEFT JOIN resource res ON res.resource_id = c.resource_id
            LEFT JOIN platform p ON p.platform_id = c.platform_id
            LEFT JOIN environment e ON e.env_id = c.env_id
            WHERE c.time >= ?
            ORDER BY c.time DESC
            """,
            (since,),
        ).fetchall()

        by_res: Dict[str, List[Any]] = defaultdict(list)
        for r in rows:
            if r["resource_id"]:
                by_res[r["resource_id"]].append(r)

        anomalies: List[Dict[str, Any]] = []

        for resource_id, items in by_res.items():
            if len(items) < 3:
                continue

            latest = items[0]
            prev_costs = [float(x["cost_usd"] or 0.0) for x in items[1:6] if (x["cost_usd"] is not None)]
            prev_costs = [x for x in prev_costs if x > 0]
            if len(prev_costs) < 2:
                continue

            med = float(median(prev_costs))
            latest_cost = float(latest["cost_usd"] or 0.0)
            if med <= 0:
                continue

            ratio = latest_cost / med
            if ratio >= spike_ratio:
                anomalies.append(
                    {
                        "resource_id": resource_id,
                        "resource_name": latest["resource_name"],
                        "resource_type": latest["resource_type"],
                        "platform": latest["platform_name"] or latest["platform_id"],
                        "env": latest["env_name"] or latest["env_id"],
                        "run_id": latest["run_id"],
                        "time": latest["time"],
                        "latest_cost_usd": latest_cost,
                        "median_prev_cost_usd": med,
                        "ratio": ratio,
                        "currency": latest["currency"],
                        "attrs": parse_json(latest["attributes_json"]),
                    }
                )

            if len(anomalies) >= limit:
                break

        lines: List[str] = []
        lines.append("COST ANOMALY REPORT")
        lines.append(f"- Window: last {days_back} days")
        lines.append(f"- Spike threshold: x{spike_ratio:.1f} vs median prior")
        lines.append(f"- Anomalies: {len(anomalies)}")
        for a in anomalies[:12]:
            lines.append(
                f"- {a['resource_name']} ({a['platform']}/{a['env']}): "
                f"${a['latest_cost_usd']:.2f} (median ${a['median_prev_cost_usd']:.2f}, x{a['ratio']:.1f}) "
                f"run={a['run_id']} time={a['time']}"
            )

        return ReportResult(
            ok=True,
            report_type="cost_anomalies",
            summary_text="\n".join(lines),
            data={"anomalies": anomalies},
        )
