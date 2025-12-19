# src/reports/lineage.py
"""
Lineage impact reports for the new Reliability Copilot schema.

Primary use:
- "What downstream assets are impacted if dataset X is wrong or late?"
- "Who depends on this table/file/stream?"

We do a BFS over dataset->dataset edges from lineage_edge.

Tables used:
- dataset, lineage_edge
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import (
    ReportResult,
    connect,
    parse_json,
    fmt_dataset_fullname,
    row_to_dict,
    safe_json,
)


def lineage_impact(
    db_path: str,
    dataset_id: str,
    *,
    depth: int = 2,
    limit_edges: int = 5000,
) -> ReportResult:
    with connect(db_path) as conn:
        start = conn.execute(
            """
            SELECT d.*, p.display_name AS platform_name, e.name AS env_name
            FROM dataset d
            LEFT JOIN platform p ON p.platform_id = d.platform_id
            LEFT JOIN environment e ON e.env_id = d.env_id
            WHERE d.dataset_id = ?
            """,
            (dataset_id,),
        ).fetchone()

        if not start:
            return ReportResult(
                ok=False,
                report_type="lineage_impact",
                summary_text=f"LINEAGE IMPACT REPORT\n- Error: dataset_id not found: {dataset_id}",
                data={"dataset_id": dataset_id},
            )

        start_name = fmt_dataset_fullname(start["namespace"], start["name"])
        start_platform = start["platform_name"] or start["platform_id"] or "logical"
        start_env = start["env_name"] or start["env_id"]

        edges = conn.execute(
            """
            SELECT src_resource_id, dst_resource_id, relation_type, attributes_json, run_id
            FROM lineage_edge
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit_edges,),
        ).fetchall()

        adj: Dict[str, List[Dict[str, Any]]] = {}
        for e in edges:
            adj.setdefault(e["src_resource_id"], []).append(
                {
                    "src_resource_id": e["src_resource_id"],
                    "dst_resource_id": e["dst_resource_id"],
                    "relation_type": e["relation_type"],
                    "run_id": e["run_id"],
                    "attrs": parse_json(e["attributes_json"]),
                }
            )

        # BFS
        visited: Set[str] = {dataset_id}
        q = deque([(dataset_id, 0)])
        downstream: List[Dict[str, Any]] = []
        used_edges: List[Dict[str, Any]] = []

        while q:
            cur, d = q.popleft()
            if d >= depth:
                continue
            for e in adj.get(cur, []):
                used_edges.append(e)
                dn = e["downstream_dataset_id"]
                if dn in visited:
                    continue
                visited.add(dn)
                q.append((dn, d + 1))

                dn_row = conn.execute(
                    """
                    SELECT d.*, p.display_name AS platform_name, e.name AS env_name
                    FROM dataset d
                    LEFT JOIN platform p ON p.platform_id = d.platform_id
                    LEFT JOIN environment e ON e.env_id = d.env_id
                    WHERE d.dataset_id = ?
                    """,
                    (dn,),
                ).fetchone()

                if dn_row:
                    downstream.append(
                        {
                            "dataset_id": dn,
                            "name": fmt_dataset_fullname(dn_row["namespace"], dn_row["name"]),
                            "dataset_type": dn_row["dataset_type"],
                            "platform": dn_row["platform_name"] or dn_row["platform_id"] or "logical",
                            "env": dn_row["env_name"] or dn_row["env_id"],
                        }
                    )
                else:
                    downstream.append({"dataset_id": dn, "name": dn, "dataset_type": None, "platform": None, "env": None})

        lines: List[str] = []
        lines.append("LINEAGE IMPACT REPORT")
        lines.append(f"- Start dataset: {start_name} (dataset_id={dataset_id})")
        lines.append(f"- Start context: {start_platform}/{start_env}")
        lines.append(f"- Depth: {depth}")
        lines.append(f"- Downstream datasets: {len(downstream)}")

        for ds in downstream[:15]:
            lines.append(f"- {ds['name']} ({ds.get('platform')}/{ds.get('env')})")

        return ReportResult(
            ok=True,
            report_type="lineage_impact",
            summary_text="\n".join(lines),
            data={
                "start_dataset": {
                    "dataset_id": dataset_id,
                    "name": start_name,
                    "dataset_type": start["dataset_type"],
                    "platform": start_platform,
                    "env": start_env,
                },
                "downstream": downstream,
                "edges": used_edges,
            },
        )
