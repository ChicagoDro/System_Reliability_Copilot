````md
# Databricks SLA Runbook

This runbook contains operational guidance for diagnosing and remediating
Databricks job SLA breaches. Each section is an independent, retrievable chunk.

---

## Chunk DBX-SLA-001
**metadata**
```yaml
chunk_id: DBX-SLA-001
platform_id: databricks
topic: sla
applies_to: [job, cluster]
severity: high
scenario_tags: [sla_breach, runtime_regression]
signals: [run_duration_increase, stage_skew, long_gc]
````

**content**
When a Databricks job breaches SLA due to a sudden runtime increase, first separate
**queue delay** from **execution delay**.

Steps:

1. Compare `run.started_at` to the first Spark activity in driver logs
   (for example, “SparkContext started”).
2. If there is a long gap, the issue is cluster acquisition or queueing.
3. If execution itself is long, analyze stages and task distribution.

Execution-focused checks:

* Look for stage skew (a small number of tasks dominate runtime).
* Look for GC pressure or memory churn in driver/executor logs.
* Identify whether the workload is SQL-heavy or Python-heavy.

Remediation should be evidence-driven:

* SQL-heavy workloads may benefit from enabling Photon.
* Skewed stages may require repartitioning or salting.
* Memory pressure may require changing executor memory/core ratios.

---

## Chunk DBX-SLA-002

**metadata**

```yaml
chunk_id: DBX-SLA-002
platform_id: databricks
topic: sla
applies_to: [job, cluster]
severity: medium
scenario_tags: [sla_breach, shuffle_bottleneck]
signals: [high_shuffle_read_write, long_stage_time]
```

**content**
If an SLA breach correlates with shuffle-heavy stages, treat it as a shuffle bottleneck.

Indicators:

* High shuffle read/write metrics.
* Long-running stages with a “long tail” of tasks.
* Fetch failures or executor loss during shuffle.

Actions:

1. Validate shuffle partition count relative to data volume.
2. Increase parallelism only if partitions are too large.
3. Prefer upstream partitioning to reduce shuffle volume.
4. If joins cause skew, consider broadcast joins or key salting.

Treat shuffle tuning as an experiment:

* Capture baseline runtime and cost.
* Change one parameter at a time.
* Persist winning configurations as named compute configs.

---

## Chunk DBX-SLA-003

**metadata**

```yaml
chunk_id: DBX-SLA-003
platform_id: databricks
topic: sla
applies_to: [job]
severity: high
scenario_tags: [sla_breach, data_volume_growth]
signals: [input_rows_increase, output_size_growth]
```

**content**
SLA breaches often result from **silent data volume growth** rather than code changes.

Evidence:

* Input row counts increase steadily over time.
* Execution time scales linearly with input size.
* No major code or configuration changes are detected.

Mitigations:

* Introduce partition pruning where possible.
* Add incremental processing instead of full refresh.
* Archive or compact historical data that is no longer queried.

Always validate whether SLA expectations still match data scale.

---

## Chunk DBX-SLA-004

**metadata**

```yaml
chunk_id: DBX-SLA-004
platform_id: databricks
topic: sla
applies_to: [job, cluster]
severity: medium
scenario_tags: [sla_breach, retries]
signals: [attempts_increase, transient_failures]
```

**content**
Repeated retries can mask SLA problems by extending total runtime.

Checklist:

* Check `run.attempt` count.
* Identify whether retries are caused by transient or permanent failures.
* Correlate retries with cost spikes.

Guidance:

* Permanent failures should not be retried.
* Transient failures (spot loss, brief network issues) may justify retries.
* Excessive retries should be capped during investigation.

---

## Chunk DBX-SLA-005

**metadata**

```yaml
chunk_id: DBX-SLA-005
platform_id: databricks
topic: sla
applies_to: [cluster]
severity: low
scenario_tags: [sla_breach, startup_delay]
signals: [cluster_start_latency]
```

**content**
Cluster startup time can contribute to SLA misses, especially for short jobs.

Actions:

* Measure time spent waiting for cluster readiness.
* Consider job clusters vs all-purpose clusters.
* For latency-sensitive workloads, keep a warm cluster available.

Cluster startup delays should be treated separately from execution inefficiency.

```
```
