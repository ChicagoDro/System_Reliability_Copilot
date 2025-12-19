```markdown
---
## Chunk RB-DBX-005
**metadata**
```yaml
chunk_id: RB-DBX-005
platform_id: databricks
topic: schema_evolution
applies_to: [job, delta]
severity: high
scenario_tags: [schema_drift, missing_column, analysis_exception]
signals: [ "AnalysisException: cannot resolve column", "schema mismatch", "missing column" ]

```

**content**

### Mitigation: Databricks Schema Drift (Missing Columns)

**Symptoms**

* Job fails with `AnalysisException: cannot resolve column "x"`.
* Merge operation fails due to schema mismatch.
* Upstream source changed schema (dropped a column) without notification.

**Resolution**

1. **Assess Impact:** Is the missing column critical?
* **Yes:** Fail the job and contact the data producer.
* **No:** Update the read logic to use `.option("mergeSchema", "true")` or provide a default value: `col("user_id").cast("long")`.


2. **Delta Schema Evolution:**
* To allow column drops/adds, enable schema evolution:
`SET spark.databricks.delta.schema.autoMerge.enabled = true`



**Prevention**

* Implement a **Schema Contract** check at the ingestion layer (e.g., Great Expectations) to catch drift before it crashes the Silver/Gold layer.

---
