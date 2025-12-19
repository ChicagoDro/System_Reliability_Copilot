# Snowflake Observability Runbook

---

## Chunk SNOW-OBS-001
**metadata**
```yaml
chunk_id: SNOW-OBS-001
platform_id: snowflake
topic: observability
applies_to: [query]
severity: high
scenario_tags: [missing_metrics]
signals: [query_history_gap]
```

**content**
Missing observability data should be treated as reduced visibility.

Actions:
- Validate query history retention.
- Correlate billing data with execution gaps.
- Avoid assuming system health during telemetry gaps.

---

## Chunk SNOW-OBS-002
**metadata**
```yaml
chunk_id: SNOW-OBS-002
platform_id: snowflake
topic: observability
applies_to: [account]
severity: medium
scenario_tags: [partial_telemetry]
signals: [incomplete_metrics]
```

**content**
Partial telemetry requires cautious interpretation.

Actions:
- Corroborate findings across multiple evidence sources.
- Document telemetry confidence during incidents.
