# src/reports/observability.py
"""
Observability integrity reports (OpenTelemetry-aware) for the new schema.

Goal:
Detect likely telemetry drop / missing signals, and provide context the copilot can cite.

Heuristics (seed-friendly):
- Metric: otelcol_exporter_send_failed > 0
- Logs: contains "dropping telemetry" or "Exporter queue is full"
- Optional: spans missing for a failed run that has logs mentioning trace/span ids (future)

Tables used:
- metric_point, log_record
Optionally:
- span, otel_resource (future deepening)
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base import ReportResult, connect, since_iso, parse_json


DEFAULT_DROP_LOG_PATTERNS = [
    "%dropping telemetry%",
    "%Exporter queue is full%",
    "%exporter queue is full%",
    "%dropped spans%",
    "%dropped logs%",
]


def observability_integrity(db_path: str, *, days_back: int = 14) -> ReportResult:
    since = since_iso(days_back)

    with connect(db_path) as conn:
        metric_rows = conn.execute(
            """
            SELECT metric_name, value_number, unit, time, attributes_json, resource_id, run_id
            FROM metric_point
            WHERE time >= ? AND metric_name IN ('otelcol_exporter_send_failed')
            ORDER BY time DESC
            LIMIT 500
            """,
            (since,),
        ).fetchall()

        log_like_clause = " OR ".join([f"body LIKE '{p}'" for p in DEFAULT_DROP_LOG_PATTERNS])
        log_rows = conn.execute(
            f"""
            SELECT time, severity_text, body, attributes_json, resource_id, run_id, trace_id, otel_span_id
            FROM log_record
            WHERE time >= ? AND ({log_like_clause})
            ORDER BY time DESC
            LIMIT 500
            """,
            (since,),
        ).fetchall()

        signals: List[Dict[str, Any]] = []

        for m in metric_rows:
            try:
                v = float(m["value_number"] or 0.0)
            except Exception:
                v = 0.0
            if v > 0:
                signals.append(
                    {
                        "type": "metric",
                        "time": m["time"],
                        "metric_name": m["metric_name"],
                        "value": m["value_number"],
                        "unit": m["unit"],
                        "resource_id": m["resource_id"],
                        "run_id": m["run_id"],
                        "attrs": parse_json(m["attributes_json"]),
                    }
                )

        for l in log_rows:
            signals.append(
                {
                    "type": "log",
                    "time": l["time"],
                    "severity": l["severity_text"],
                    "body": l["body"],
                    "resource_id": l["resource_id"],
                    "run_id": l["run_id"],
                    "trace_id": l["trace_id"],
                    "otel_span_id": l["otel_span_id"],
                    "attrs": parse_json(l["attributes_json"]),
                }
            )

        ok = len(signals) == 0
        lines: List[str] = []
        lines.append("OBSERVABILITY INTEGRITY REPORT")
        lines.append(f"- Window: last {days_back} days")
        lines.append(f"- Signals: {len(signals)}")
        if ok:
            lines.append("- No evidence of telemetry drop detected.")
        else:
            lines.append("- Possible telemetry drop detected. Treat missing logs/spans/metrics with caution.")
            # show top 10
            for s in signals[:10]:
                if s["type"] == "metric":
                    lines.append(f"- [{s['time']}] metric {s['metric_name']}={s['value']}")
                else:
                    lines.append(f"- [{s['time']}] log {s['severity']}: {s['body']}")

        return ReportResult(
            ok=True,
            report_type="observability_integrity",
            summary_text="\n".join(lines),
            data={"signals": signals, "ok_no_drop_detected": ok},
        )
