```md
# Airflow Incident Runbook

---

## Chunk AF-INC-001
**metadata**
```yaml
chunk_id: AF-INC-001
platform_id: airflow
topic: incidents
applies_to: [dag, task]
severity: high
scenario_tags: [task_failure, sensor_timeout]
signals: [task_failed, upstream_failed, sensor_timeout]

```

**content**
When an Airflow task fails, isolate whether the failure is **logic-based** (code error) or **dependency-based** (missing data/resource).

**Triage Steps:**

1. Check the Task Instance logs (Standard Out).
2. If the error is `SensorTimeout`, the upstream data never arrived. Check the source system.
3. If the error is `AirflowException` or `PythonOperator` failure, check the stack trace for code bugs.
4. If the status is `upstream_failed`, do not debug this task; find the root failure in the upstream task.

**Action:**

* For sensors: Verify file arrival in S3/GCS.
* For logic errors: Fix code and clear task state to retry.

---

## Chunk AF-DQ-001

**metadata**

```yaml
chunk_id: AF-DQ-001
platform_id: airflow
topic: dq
applies_to: [dag, dataset]
severity: medium
scenario_tags: [empty_file, data_quality]
signals: [row_count_zero, file_size_zero]

```

**content**
Pipelines often fail validation because source files are present but empty (0 bytes or header-only).

**Evidence:**

* DQ check `row_count > 0` fails.
* Log shows "File downloaded. Size: 0 bytes."

**Mitigation:**

1. Implement a "Sensor" that checks for non-zero size, not just file existence.
2. Contact the data vendor/provider to re-send the file.
3. Mark the DAG run as failed; do not skip, as this hides data loss.

```