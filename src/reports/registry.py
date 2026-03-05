# src/reports/registry.py
from __future__ import annotations
from typing import Dict, List
from src.reports.base import ReportSpec

from src.reports.failing_resources import REPORT as FAILING_REPORT
from src.reports.sla_breaches import REPORT as SLA_REPORT
from src.reports.service_health import REPORT as SERVICE_REPORT


def get_reports() -> List[ReportSpec]:
    return [
        FAILING_REPORT,
        SLA_REPORT,
        SERVICE_REPORT,
    ]


def get_report_map() -> Dict[str, ReportSpec]:
    return {r.key: r for r in get_reports()}


def get_default_report_key() -> str:
    reports = get_reports()
    return "failing_resources" if reports else ""
