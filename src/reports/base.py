# src/reports/base.py
"""
Shared utilities + base types for the new cross-platform Reliability Copilot reports.

This replaces your old src/reports/base.py (Databricks-specific) with a platform-agnostic foundation.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol


class SelectionLike(Protocol):
    """
    Minimal interface that Streamlit app expects from a report selection.
    """
    entity_type: str
    entity_id: str
    label: str



# ----------------------------
# Core result type
# ----------------------------

@dataclass
class ReportResult:
    ok: bool
    report_type: str
    summary_text: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "type": self.report_type,
            "summary_text": self.summary_text,
            **self.data,
        }


# ----------------------------
# DB helpers
# ----------------------------

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def since_iso(days_back: int) -> str:
    dt = datetime.now() - timedelta(days=days_back)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------
# JSON helpers
# ----------------------------

def parse_json(s: Optional[str]) -> Dict[str, Any]:
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {"_raw": s}


def safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(obj)


# ----------------------------
# Common formatters
# ----------------------------

def fmt_platform_env(platform_name: Optional[str], platform_id: Optional[str], env_name: Optional[str], env_id: Optional[str]) -> str:
    plat = platform_name or platform_id or "unknown_platform"
    env = env_name or env_id or "unknown_env"
    return f"{plat}/{env}"


def fmt_dataset_fullname(namespace: Optional[str], name: Optional[str]) -> str:
    return f"{(namespace or '').strip()}.{(name or '').strip()}".strip(".")


def top_n_lines(lines: List[str], n: int) -> str:
    if len(lines) <= n:
        return "\n".join(lines)
    return "\n".join(lines[:n]) + f"\n... ({len(lines) - n} more)"


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}
