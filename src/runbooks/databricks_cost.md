````md
# Databricks Cost Optimization Runbook

This runbook contains operational guidance for diagnosing and remediating
Databricks cost anomalies, including sudden DBU spikes and inefficient compute usage.

---

## Chunk DBX-COST-001
**metadata**
```yaml
chunk_id: DBX-COST-001
platform_id: databricks
topic: cost
applies_to: [job]
severity: high
scenario_tags: [cost_spike, retries]
signals: [attempts_increase, repeated_failures]
````

**content**
A common cause of Databricks cost spikes is repeated retries of failing jobs.

Evidence:

* Multiple attempts for the same logical workload.
* Logs show the same failure repeating.
* Cost records increase with each retry.

Actions:

1. Reduce or temporarily disable retries.
2. Identify whether failures are permanent or transient.
3. Fix permanent failures before re-enabling retries.

Retries should protect against instability, not amplify waste.

---

## Chunk DBX-COST-002

**metadata**

```yaml
chunk_id: DBX-COST-002
platform_id: databricks
topic: cost
applies_to: [cluster]
severity: high
scenario_tags: [cost_spike, overprovisioning]
signals: [low_cpu_utilization, idle_executors]
```

**content**
Overprovisioned clusters are a frequent source of unnecessary DBU spend.

Indicators:

* Low average CPU utilization.
* Short-lived tasks with high scheduling overhead.
* Cluster runs much longer than actual work.

Mitigation:

* Reduce worker count or instance size.
* Enable autoscaling with a reasonable minimum.
* Right-size clusters based on observed utilization, not peak assumptions.

---

## Chunk DBX-COST-003

**metadata**

```yaml
chunk_id: DBX-COST-003
platform_id: databricks
topic: cost
applies_to: [job]
severity: medium
scenario_tags: [cost_spike, inefficient_code]
signals: [long_runtime, low_throughput]
```

**content**
Inefficient transformations can inflate cost even when clusters are sized correctly.

Signs:

* Long runtimes with modest data volumes.
* Heavy use of Python UDFs.
* Repeated wide transformations.

Actions:

* Prefer native Spark SQL functions.
* Reduce unnecessary wide transformations.
* Cache only when reuse justifies the memory cost.

---

## Chunk DBX-COST-004

**metadata**

```yaml
chunk_id: DBX-COST-004
platform_id: databricks
topic: cost
applies_to: [cluster]
severity: medium
scenario_tags: [cost_spike, spot_instances]
signals: [executor_loss, retries]
```

**content**
Spot or preemptible instances reduce cost but can increase retries and runtime.

Guidance:

* Confirm workloads tolerate executor loss.
* Limit spot fraction for SLA-critical jobs.
* Monitor whether spot interruptions correlate with retries and cost spikes.

---

## Chunk DBX-COST-005

**metadata**

```yaml
chunk_id: DBX-COST-005
platform_id: databricks
topic: cost
applies_to: [job]
severity: low
scenario_tags: [cost_trend, growth]
signals: [gradual_cost_increase]
```

**content**
Gradual cost increases often reflect data growth rather than regressions.

Actions:

* Track cost per unit of data processed.
* Re-evaluate data retention policies.
* Align cost expectations with data scale growth.

Cost trending should be reviewed periodically, not only during incidents.

```
```
