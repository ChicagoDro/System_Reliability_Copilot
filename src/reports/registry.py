# src/reports/registry.py
from __future__ import annotations
from typing import Dict, List
from src.reports.base import ReportSpec

from src.reports.recent_incidents import REPORT as INCIDENTS_REPORT
from src.reports.failing_resources import REPORT as FAILING_REPORT
from src.reports.run_history import REPORT as HISTORY_REPORT
from src.reports.metric_anomalies import REPORT as METRICS_REPORT
from src.reports.log_patterns import REPORT as LOGS_REPORT
from src.reports.sla_breaches import REPORT as SLA_REPORT
from src.reports.cost_overview import REPORT as COST_REPORT # <--- NEW

def get_reports() -> List[ReportSpec]:
    return [
        INCIDENTS_REPORT,
        FAILING_REPORT,
        HISTORY_REPORT,
        SLA_REPORT,
        COST_REPORT, # <--- NEW
        METRICS_REPORT,
        LOGS_REPORT,
    ]

def get_report_map() -> Dict[str, ReportSpec]:
    return {r.key: r for r in get_reports()}

def get_default_report_key() -> str:
    reports = get_reports()
    return "recent_incidents" if reports else ""