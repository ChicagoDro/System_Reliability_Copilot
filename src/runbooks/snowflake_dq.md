# Snowflake Data Quality Runbook

---

## Chunk SNOW-DQ-001
**metadata**
```yaml
chunk_id: SNOW-DQ-001
platform_id: snowflake
topic: dq
applies_to: [table]
severity: high
scenario_tags: [dq_failure, schema_change]
signals: [type_mismatch, null_spike]
```

**content**
Schema changes in upstream sources frequently cause Snowflake data quality failures.

Actions:
- Validate upstream schema changes.
- Review COPY INTO error handling.
- Enforce explicit column mappings instead of positional loads.

---

## Chunk SNOW-DQ-002
**metadata**
```yaml
chunk_id: SNOW-DQ-002
platform_id: snowflake
topic: dq
applies_to: [table]
severity: medium
scenario_tags: [dq_failure, freshness]
signals: [stale_data]
```

**content**
Freshness failures often result from delayed upstream ingestion.

Actions:
- Validate upstream task completion.
- Separate late data alerts from pipeline failures.
- Implement backfill strategies for late-arriving data.
