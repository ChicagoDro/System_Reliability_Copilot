# src/ingest_reliability_domain.py
"""
Build RAG documents for the Reliability Copilot SQLite schema.

Compatibility goals:
- Produces RagDoc objects that work with ingest_embed_index.py
  (doc_id, text, metadata) but also tolerates older/newer call sites
  that pass title/tags.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ----------------------------
# Core doc structure (flexible)
# ----------------------------

@dataclass
class RagDoc:
    doc_id: str
    text: str
    metadata: Optional[Dict[str, Any]] = field(default=None)

    # Optional fields: allow older/newer code paths that pass these
    title: Optional[str] = None
    tags: Optional[List[str]] = None


# ----------------------------
# SQLite helpers
# ----------------------------

def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Ensure FKs are enforced for reads/writes in same connection
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _parse_json(s: Optional[str]) -> Dict[str, Any]:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {"_raw": s}


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(obj)


def _has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    return any(r["name"] == col for r in rows)


# ----------------------------
# Doc builders
# ----------------------------

def _fetch_resource_summaries(conn: sqlite3.Connection) -> List[RagDoc]:
    """
    Your current schema:
      environment(env_id, env_type, region, attributes_json)
      resource(resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, created_at)
      platform(platform_id, platform_type, display_name, attributes_json)
    Some older schema variants might have:
      resource.is_active
      environment.name
    """
    has_is_active = _has_column(conn, "resource", "is_active")
    has_env_name = _has_column(conn, "environment", "name")

    # Select env display name if present; otherwise fall back to env_id.
    env_name_expr = "e.name" if has_env_name else "e.env_id"
    # Select is_active if present; otherwise treat as active.
    is_active_expr = "r.is_active" if has_is_active else "1 AS is_active"

    sql = f"""
    SELECT
      r.resource_id, r.platform_id, r.env_id, r.resource_type, r.external_id,
      r.name, r.namespace, r.owner, {is_active_expr}, r.attributes_json,
      p.display_name AS platform_name,
      {env_name_expr} AS env_name
    FROM resource r
    LEFT JOIN platform p ON p.platform_id = r.platform_id
    LEFT JOIN environment e ON e.env_id = r.env_id
    ORDER BY r.platform_id, r.env_id, r.resource_type, r.name
    """

    rows = conn.execute(sql).fetchall()

    docs: List[RagDoc] = []
    for r in rows:
        attrs = _parse_json(r["attributes_json"])
        is_active = bool(r["is_active"]) if r["is_active"] is not None else True

        docs.append(
            RagDoc(
                doc_id=f"resource:{r['resource_id']}",
                title=f"Resource: {r['name']}",
                tags=["resource", r["platform_id"], r["env_id"], r["resource_type"]],
                metadata={
                    "kind": "resource",
                    "resource_id": r["resource_id"],
                    "platform_id": r["platform_id"],
                    "env_id": r["env_id"],
                    "resource_type": r["resource_type"],
                    "external_id": r["external_id"],
                    "namespace": r["namespace"],
                    "owner": r["owner"],
                    "is_active": is_active,
                },
                text=(
                    "RESOURCE SUMMARY\n"
                    f"- Name: {r['name']}\n"
                    f"- Type: {r['resource_type']}\n"
                    f"- Platform: {r['platform_name'] or r['platform_id']}\n"
                    f"- Environment: {r['env_name'] or r['env_id']}\n"
                    f"- Namespace: {r['namespace']}\n"
                    f"- Owner: {r['owner']}\n"
                    f"- External ID: {r['external_id']}\n"
                    f"- Active: {is_active}\n"
                    f"- Attributes: {_safe_json(attrs)}\n"
                ),
            )
        )
    return docs


def _fetch_recent_runs(conn: sqlite3.Connection, days_back: int) -> List[RagDoc]:
    sql = """
    SELECT
      run_id, platform_id, env_id, resource_id,
      external_run_id, run_type, status, attempt,
      started_at, ended_at, message, attributes_json
    FROM run
    WHERE started_at >= datetime('now', ?)
    ORDER BY started_at DESC
    LIMIT 500
    """
    rows = conn.execute(sql, (f"-{days_back} days",)).fetchall()

    docs: List[RagDoc] = []
    for r in rows:
        attrs = _parse_json(r["attributes_json"])
        docs.append(
            RagDoc(
                doc_id=f"run:{r['run_id']}",
                title=f"Run: {r['run_id']}",
                tags=["run", r["platform_id"], r["env_id"], r["status"]],
                metadata={
                    "kind": "run",
                    "run_id": r["run_id"],
                    "platform_id": r["platform_id"],
                    "env_id": r["env_id"],
                    "resource_id": r["resource_id"],
                    "external_run_id": r["external_run_id"],
                    "status": r["status"],
                },
                text=(
                    "RUN\n"
                    f"- run_id: {r['run_id']}\n"
                    f"- platform_id: {r['platform_id']}\n"
                    f"- env_id: {r['env_id']}\n"
                    f"- resource_id: {r['resource_id']}\n"
                    f"- external_run_id: {r['external_run_id']}\n"
                    f"- run_type: {r['run_type']}\n"
                    f"- status: {r['status']}\n"
                    f"- attempt: {r['attempt']}\n"
                    f"- started_at: {r['started_at']}\n"
                    f"- ended_at: {r['ended_at']}\n"
                    f"- message: {r['message']}\n"
                    f"- attributes: {_safe_json(attrs)}\n"
                ),
            )
        )
    return docs


def _fetch_metrics(conn: sqlite3.Connection, days_back: int) -> List[RagDoc]:
    sql = """
    SELECT
      metric_point_id, metric_name, metric_type, unit, value_number, value_json,
      resource_id, run_id, time, start_time, attributes_json
    FROM metric_point
    WHERE time >= datetime('now', ?)
    ORDER BY time DESC
    LIMIT 800
    """
    rows = conn.execute(sql, (f"-{days_back} days",)).fetchall()

    docs: List[RagDoc] = []
    for r in rows:
        attrs = _parse_json(r["attributes_json"])
        docs.append(
            RagDoc(
                doc_id=f"metric:{r['metric_point_id']}",
                title=f"Metric: {r['metric_name']}",
                tags=["metric", r["metric_name"], r["metric_type"]],
                metadata={
                    "kind": "metric_point",
                    "metric_point_id": r["metric_point_id"],
                    "metric_name": r["metric_name"],
                    "resource_id": r["resource_id"],
                    "run_id": r["run_id"],
                    "time": r["time"],
                },
                text=(
                    "METRIC POINT\n"
                    f"- metric_name: {r['metric_name']}\n"
                    f"- metric_type: {r['metric_type']}\n"
                    f"- unit: {r['unit']}\n"
                    f"- value_number: {r['value_number']}\n"
                    f"- value_json: {r['value_json']}\n"
                    f"- resource_id: {r['resource_id']}\n"
                    f"- run_id: {r['run_id']}\n"
                    f"- start_time: {r['start_time']}\n"
                    f"- time: {r['time']}\n"
                    f"- attributes: {_safe_json(attrs)}\n"
                ),
            )
        )
    return docs


def _fetch_logs(conn: sqlite3.Connection, days_back: int) -> List[RagDoc]:
    sql = """
    SELECT
      log_id, severity_text, body, resource_id, run_id, time, attributes_json
    FROM log_record  -- <--- UPDATE THIS LINE (was log_event)
    WHERE time >= datetime('now', ?)
    ORDER BY time DESC
    LIMIT 800
    """
    rows = conn.execute(sql, (f"-{days_back} days",)).fetchall()

    docs: List[RagDoc] = []
    for r in rows:
        attrs = _parse_json(r["attributes_json"])
        docs.append(
            RagDoc(
                doc_id=f"log:{r['log_id']}",
                title=f"Log: {r['log_id']}",
                tags=["log", (r["severity_text"] or "UNKNOWN")],
                metadata={
                    "kind": "log_event",
                    "log_id": r["log_id"],
                    "severity_text": r["severity_text"],
                    "resource_id": r["resource_id"],
                    "run_id": r["run_id"],
                    "time": r["time"],
                },
                text=(
                    "LOG EVENT\n"
                    f"- log_id: {r['log_id']}\n"
                    f"- severity_text: {r['severity_text']}\n"
                    f"- resource_id: {r['resource_id']}\n"
                    f"- run_id: {r['run_id']}\n"
                    f"- time: {r['time']}\n"
                    f"- body: {r['body']}\n"
                    f"- attributes: {_safe_json(attrs)}\n"
                ),
            )
        )
    return docs


def _fetch_incidents(conn: sqlite3.Connection, days_back: int) -> List[RagDoc]:
    sql = """
    SELECT
      incident_id, env_id, title, severity, status,
      opened_at, closed_at, summary, attributes_json
    FROM incident
    WHERE opened_at >= datetime('now', ?)
    ORDER BY opened_at DESC
    LIMIT 300
    """
    rows = conn.execute(sql, (f"-{days_back} days",)).fetchall()

    docs: List[RagDoc] = []
    for r in rows:
        attrs = _parse_json(r["attributes_json"])
        docs.append(
            RagDoc(
                doc_id=f"incident:{r['incident_id']}",
                title=f"Incident: {r['title']}",
                tags=["incident", r["severity"], r["status"]],
                metadata={
                    "kind": "incident",
                    "incident_id": r["incident_id"],
                    "env_id": r["env_id"],
                    "severity": r["severity"],
                    "status": r["status"],
                },
                text=(
                    "INCIDENT\n"
                    f"- incident_id: {r['incident_id']}\n"
                    f"- env_id: {r['env_id']}\n"
                    f"- title: {r['title']}\n"
                    f"- severity: {r['severity']}\n"
                    f"- status: {r['status']}\n"
                    f"- opened_at: {r['opened_at']}\n"
                    f"- closed_at: {r['closed_at']}\n"
                    f"- summary: {r['summary']}\n"
                    f"- attributes: {_safe_json(attrs)}\n"
                ),
            )
        )
    return docs


def _fetch_lineage(conn: sqlite3.Connection) -> List[RagDoc]:
    # lineage_edge exists in your current schema
    sql = """
    SELECT edge_id, env_id, src_resource_id, dst_resource_id, relation_type, attributes_json
    FROM lineage_edge
    ORDER BY created_at DESC
    LIMIT 500
    """
    try:
        rows = conn.execute(sql).fetchall()
    except sqlite3.OperationalError:
        return []

    docs: List[RagDoc] = []
    for r in rows:
        attrs = _parse_json(r["attributes_json"])
        docs.append(
            RagDoc(
                doc_id=f"lineage:{r['edge_id']}",
                title=f"Lineage edge {r['edge_id']}",
                tags=["lineage", r["relation_type"], r["env_id"]],
                metadata={
                    "kind": "lineage_edge",
                    "edge_id": r["edge_id"],
                    "env_id": r["env_id"],
                    "src_resource_id": r["src_resource_id"],
                    "dst_resource_id": r["dst_resource_id"],
                    "relation_type": r["relation_type"],
                },
                text=(
                    "LINEAGE EDGE\n"
                    f"- edge_id: {r['edge_id']}\n"
                    f"- env_id: {r['env_id']}\n"
                    f"- src_resource_id: {r['src_resource_id']}\n"
                    f"- dst_resource_id: {r['dst_resource_id']}\n"
                    f"- relation_type: {r['relation_type']}\n"
                    f"- attributes: {_safe_json(attrs)}\n"
                ),
            )
        )
    return docs


# ----------------------------
# Public entrypoint
# ----------------------------

def build_reliability_rag_docs(db_path: str, mode: str = "lite", days_back: Optional[int] = None) -> List[RagDoc]:
    """
    mode: lite|demo (used mainly for defaults)
    days_back: optional override. If None, we choose a reasonable default.
    """
    # Default lookbacks (safe & deterministic)
    if days_back is None:
        # demo has richer data; still keep reasonable
        days_back_effective = 120 if mode == "demo" else 90
    else:
        days_back_effective = int(days_back)

    docs: List[RagDoc] = []
    with _get_conn(db_path) as conn:
        docs.extend(_fetch_resource_summaries(conn))
        docs.extend(_fetch_recent_runs(conn, days_back=days_back_effective))
        docs.extend(_fetch_metrics(conn, days_back=days_back_effective))
        docs.extend(_fetch_logs(conn, days_back=days_back_effective))
        docs.extend(_fetch_incidents(conn, days_back=max(days_back_effective, 90)))
        docs.extend(_fetch_lineage(conn))

    # Ensure metadata is always a dict (so ingest_embed_index can do **metadata safely)
    for d in docs:
        if d.metadata is None:
            d.metadata = {}
        if d.title and "title" not in d.metadata:
            d.metadata["title"] = d.title
        if d.tags and "tags" not in d.metadata:
            d.metadata["tags"] = d.tags
        d.metadata.setdefault("mode", mode)

    return docs

# ... (end of your existing code)

if __name__ == "__main__":
    # Adjust db_path as needed for your project structure
    docs = build_reliability_rag_docs("data/reliability.db", mode="demo")
    print(f"Successfully built {len(docs)} RAG documents.")
    # Add logic here if you need to save 'docs' somewhere