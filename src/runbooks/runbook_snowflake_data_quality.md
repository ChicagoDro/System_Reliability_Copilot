
```markdown
---
## Chunk RB-SNOW-009
**metadata**
```yaml
chunk_id: RB-SNOW-009
platform_id: snowflake
topic: data_recovery
applies_to: [table, schema, database]
severity: critical
scenario_tags: [data_loss, truncated_table, zero_rows, time_travel]
signals: [ "row_count = 0", "table empty", "accidental truncate" ]

```

**content**

### Procedure: Recovering from Accidental Data Loss (Time Travel)

**Symptoms**

* A critical table (e.g., Customers) suddenly reports `0` rows.
* Downstream dashboards are blank.
* Alert: `Metric Anomaly: row_count dropped to 0`.

**Resolution: Snowflake Time Travel**
Do **NOT** run the ETL pipeline again (it might overwrite the history). Use Snowflake Time Travel immediately.

1. **Identify Timestamp:** Find the time *before* the data loss occurred (e.g., from `metric_point` history).
2. **Run Undrop / Clone:**
```sql
-- Option A: Restore table to previous state
CREATE OR REPLACE TABLE db.public.customers AS
SELECT * FROM db.public.customers AT(OFFSET => -60*60*2); -- Go back 2 hours

```


3. **Verify:** Check row count matches the historical baseline (~10.5k rows).

**Escalation**

* **Sev-1 Incident:** This is a critical data loss event. Notify **Privacy/Governance** if PII was lost or exposed.
* Page **Analytics Engineering** (@analytics-eng).

---
