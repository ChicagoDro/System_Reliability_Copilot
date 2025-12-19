# src/reports/registry.py
from __future__ import annotations
from typing import Dict, List
from src.reports.base import ReportSpec

# Import new Reliability Reports
from src.reports.recent_incidents import REPORT as INCIDENTS_REPORT
from src.reports.failing_resources import REPORT as FAILING_REPORT

def get_reports() -> List[ReportSpec]:
    """
    Ordered list used for sidebar navigation.
    """
    return [
        INCIDENTS_REPORT,
        FAILING_REPORT,
    ]

def get_report_map() -> Dict[str, ReportSpec]:
    return {r.key: r for r in get_reports()}

def get_default_report_key() -> str:
    reports = get_reports()
    # Default to Incidents if available, else whatever is first
    return "recent_incidents" if reports else ""