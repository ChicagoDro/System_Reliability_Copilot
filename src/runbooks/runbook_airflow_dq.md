```markdown
---
## Chunk RB-AF-001
**metadata**
```yaml
chunk_id: RB-AF-001
platform_id: airflow
topic: data_ingestion
applies_to: [dag, sensor]
severity: medium
scenario_tags: [empty_file, zero_byte, sftp, ingestion]
signals: [ "File size is 0 bytes", "DQ Rule Failed: row_count > 0", "DQ Validation Failed" ]

```

**content**

### Mitigation: Airflow Ingestion of Empty Files

**Symptoms**

* DAG fails with `DQ Validation Failed`.
* Logs show "File size is 0 bytes" or "Row count: 0".
* Vendor file arrived but contains only a header.

**Root Cause**

* The upstream vendor generated an empty manifest.
* SFTP transfer was interrupted, leaving a partial file.

**Remediation**

1. **Verify Source:** Check the SFTP/S3 bucket manually. If the file is 0 bytes there, contact the vendor.
2. **Reprocess:** If a valid file is available, clear the specific `extract_task` in Airflow to retry.
3. **Patch Logic:** Update the `FileSensor` to check for `size > 100b` instead of just existence.

**Escalation**

* If vendor confirms data was sent, check the **Transfer Service** logs for network drops.

---
