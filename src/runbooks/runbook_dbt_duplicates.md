```markdown
---
## Chunk RB-DBT-002
**metadata**
```yaml
chunk_id: RB-DBT-002
platform_id: dbt
topic: data_quality
applies_to: [model, test]
severity: low
scenario_tags: [duplicates, primary_key, unique_test]
signals: [ "unique_fct_monthly_kpis_id", "Got 5 failing rows", "Primary key violation" ]

```

**content**

### Mitigation: dbt Model Duplication (Unique Test Failed)

**Symptoms**

* dbt build fails on `test` step.
* Error: `Failure in test unique_... Got X failing rows`.
* Dashboard shows inflated numbers due to double-counting.

**Debugging Steps**

1. **Isolate Duplicates:**
```sql
SELECT id, count(*) FROM fct_monthly_kpis GROUP BY 1 HAVING count(*) > 1;

```


2. **Check Joins:** Did a `LEFT JOIN` on a non-unique key cause a fan-out?
3. **Check Source:** Are there duplicates in the raw `stg_` tables?

**Fixes**

* **Logic:** Add `QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated_at DESC) = 1` to deduplicate.
* **Data:** If source is bad, run a `dbt snapshot` to capture the state before cleaning.

---
