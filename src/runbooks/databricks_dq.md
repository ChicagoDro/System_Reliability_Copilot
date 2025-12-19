````md
# Databricks Data Quality Runbook

This runbook contains operational guidance for diagnosing and remediating
data quality failures in Databricks pipelines.

---

## Chunk DBX-DQ-001
**metadata**
```yaml
chunk_id: DBX-DQ-001
platform_id: databricks
topic: dq
applies_to: [job, dataset]
severity: high
scenario_tags: [dq_failure, schema_drift]
signals: [sudden_nulls, type_change, unexpected_columns]
````

**content**
When data quality checks begin failing due to schema-related issues, first confirm
whether **schema drift** has occurred upstream.

Evidence:

* New columns appear unexpectedly.
* Column data types change (for example, string to integer).
* NOT NULL or type-based checks suddenly fail across many rows.

Actions:

1. Identify where schema inference is used (CSV, JSON, Auto Loader, permissive modes).
2. Replace inference with explicit schemas where possible.
3. Decide on an evolution policy:

   * Fail fast on breaking changes.
   * Allow additive changes but block destructive ones.
4. For Delta tables, avoid silent schema evolution unless governance explicitly allows it.

---

## Chunk DBX-DQ-002

**metadata**

```yaml
chunk_id: DBX-DQ-002
platform_id: databricks
topic: dq
applies_to: [dataset]
severity: medium
scenario_tags: [dq_failure, freshness_violation]
signals: [freshness_check_fail, missing_partition, delayed_upstream]
```

**content**
Freshness violations often occur when upstream data arrives late rather than when
the pipeline itself is broken.

Evidence:

* Freshness checks fail while the job status is successful.
* Expected partitions are missing or delayed.
* Upstream ingestion jobs are late or absent.

Actions:

1. Validate upstream job completion and partition availability.
2. Short-circuit downstream processing when upstream data is missing.
3. Separate “data late” alerts from “pipeline failed” alerts.
4. If late data is expected, implement controlled backfill logic with clear traceability.

---

## Chunk DBX-DQ-003

**metadata**

```yaml
chunk_id: DBX-DQ-003
platform_id: databricks
topic: dq
applies_to: [dataset]
severity: high
scenario_tags: [dq_failure, null_spike]
signals: [null_rate_increase, constraint_violation]
```

**content**
A sudden spike in NULL values typically indicates upstream extraction or join issues.

Evidence:

* NULL rates increase abruptly for specific columns.
* NOT NULL constraints or expectations fail.
* Joins introduce unexpected NULLs after schema changes.

Actions:

* Inspect recent join logic changes.
* Validate join keys for completeness and type alignment.
* Check upstream source systems for missing or malformed data.
* Consider quarantining affected partitions until corrected.

---

## Chunk DBX-DQ-004

**metadata**

```yaml
chunk_id: DBX-DQ-004
platform_id: databricks
topic: dq
applies_to: [dataset]
severity: medium
scenario_tags: [dq_failure, duplicate_rows]
signals: [uniqueness_violation, row_count_increase]
```

**content**
Duplicate records are a common data quality issue in distributed pipelines.

Evidence:

* Uniqueness checks fail.
* Row counts increase faster than expected.
* Incremental pipelines reprocess overlapping data.

Actions:

* Verify incremental boundaries and watermark logic.
* Ensure idempotent writes when reprocessing data.
* Use deduplication logic explicitly rather than relying on upstream guarantees.

---

## Chunk DBX-DQ-005

**metadata**

```yaml
chunk_id: DBX-DQ-005
platform_id: databricks
topic: dq
applies_to: [job, dataset]
severity: low
scenario_tags: [dq_failure, expectation_mismatch]
signals: [rule_failure_without_data_change]
```

**content**
Sometimes data quality checks fail even though the data itself has not changed.

Evidence:

* Expectation logic was modified.
* Thresholds were tightened without baseline analysis.
* New checks were added without historical validation.

Actions:

* Review recent changes to DQ rules.
* Validate expectations against historical data.
* Roll out new or stricter rules in monitoring mode before enforcing failures.
