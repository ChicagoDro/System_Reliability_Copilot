# Snowflake Lineage Impact Runbook

---

## Chunk SNOW-LIN-001
**metadata**
```yaml
chunk_id: SNOW-LIN-001
platform_id: snowflake
topic: lineage
applies_to: [table, view]
severity: high
scenario_tags: [downstream_impact]
signals: [view_dependency]
```

**content**
Downstream views and BI tools may be impacted by upstream table changes.

Actions:
- Identify dependent views.
- Communicate impact to consumers.
- Use time travel to restore previous states if necessary.

---

## Chunk SNOW-LIN-002
**metadata**
```yaml
chunk_id: SNOW-LIN-002
platform_id: snowflake
topic: lineage
applies_to: [table]
severity: medium
scenario_tags: [lineage_confidence]
signals: [inferred_dependencies]
```

**content**
Inferred lineage should be treated with lower confidence.

Actions:
- Confirm dependencies via access history.
- Communicate uncertainty explicitly.
