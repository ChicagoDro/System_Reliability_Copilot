````md
# dbt Incident Runbook

---

## Chunk DBT-DQ-001
**metadata**
```yaml
chunk_id: DBT-DQ-001
platform_id: dbt
topic: dq
applies_to: [model, test]
severity: medium
scenario_tags: [test_failure, uniqueness]
signals: [unique_test_failed, constraint_violation]

```

**content**
A failure in a `unique` or `not_null` test indicates that the transformation logic or source data has violated assumptions.

**Investigation:**

1. Run the failing test SQL manually in the warehouse to inspect the offending rows.
* `select * from <model> where <id> in (select <id> from <model> group by <id> having count(*) > 1)`


2. Check if the duplication occurred during a `join` (fan-out) or exists in the raw source.

**Fixes:**

* If source data is bad: Filter duplicates using `qualify row_number() ...`.
* If logic is bad: Fix the join condition.

---

## Chunk DBT-RUN-001

**metadata**

```yaml
chunk_id: DBT-RUN-001
platform_id: dbt
topic: incidents
applies_to: [model]
severity: high
scenario_tags: [build_error, sql_error]
signals: [database_error, compilation_error]

```

**content**
Model build failures usually stem from SQL syntax errors or warehouse resource limits.

**Actions:**

1. Check `dbt.log` for the exact database error message.
2. If "Relation does not exist": Ensure upstream dependencies ran successfully (`dbt run` order).
3. If "Memory limit exceeded" or "Timeout": Increase warehouse size or optimize the query (reduce scans).