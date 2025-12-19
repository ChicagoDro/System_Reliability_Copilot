````md
# Snowflake SLA Runbook

This runbook contains operational guidance for diagnosing and remediating
Snowflake query and pipeline SLA breaches, focusing on warehouse behavior,
concurrency, and query execution characteristics.

---

## Chunk SNOW-SLA-001
**metadata**
```yaml
chunk_id: SNOW-SLA-001
platform_id: snowflake
topic: sla
applies_to: [query, warehouse]
severity: high
scenario_tags: [sla_breach, queueing_delay]
signals: [queued_time_increase, concurrency_pressure]
````

**content**
When Snowflake queries breach SLA, first determine whether the delay is caused by
**queueing** rather than execution.

Evidence:

* Query history shows significant queued time.
* Execution time is relatively stable compared to baseline.
* Multiple concurrent queries target the same warehouse.

Actions:

1. Inspect warehouse queueing metrics.
2. Confirm whether concurrency exceeds warehouse capacity.
3. Consider enabling multi-cluster warehouses for concurrent workloads.
4. Separate latency-sensitive queries onto dedicated warehouses if needed.

Queueing issues should be addressed at the warehouse level, not by query tuning.

---

## Chunk SNOW-SLA-002

**metadata**

```yaml
chunk_id: SNOW-SLA-002
platform_id: snowflake
topic: sla
applies_to: [query]
severity: high
scenario_tags: [sla_breach, execution_regression]
signals: [execution_time_increase, scan_bytes_growth]
```

**content**
Execution-time regressions often result from increased data scanned or reduced
pruning effectiveness.

Evidence:

* Bytes scanned per query increase.
* Execution plans show full table scans.
* Partition pruning or clustering effectiveness decreases.

Actions:

* Review filter predicates for pruning effectiveness.
* Validate clustering keys and recluster if necessary.
* Avoid functions on filter columns that prevent pruning.

Execution tuning should focus on reducing scanned data volume.

---

## Chunk SNOW-SLA-003

**metadata**

```yaml
chunk_id: SNOW-SLA-003
platform_id: snowflake
topic: sla
applies_to: [warehouse]
severity: medium
scenario_tags: [sla_breach, warehouse_sizing]
signals: [long_execution_time, cpu_pressure]
```

**content**
Under-sized warehouses can cause consistent SLA misses even without queueing.

Evidence:

* Execution time improves when concurrency is low.
* Queries are CPU-bound rather than queued.
* Warehouse size remains static despite data growth.

Actions:

* Increase warehouse size incrementally and remeasure.
* Compare cost vs latency tradeoffs.
* Use different warehouse sizes for batch vs interactive workloads.

Warehouse sizing should evolve with workload characteristics.

---

## Chunk SNOW-SLA-004

**metadata**

```yaml
chunk_id: SNOW-SLA-004
platform_id: snowflake
topic: sla
applies_to: [query]
severity: medium
scenario_tags: [sla_breach, result_cache]
signals: [cache_miss, repeated_queries]
```

**content**
Repeated queries missing the result cache can contribute to SLA breaches.

Evidence:

* Identical queries execute fully instead of returning cached results.
* Underlying tables change frequently.
* Session or role context differs across executions.

Actions:

* Confirm whether underlying data changes invalidate the cache.
* Normalize query text and execution context where possible.
* Avoid unnecessary query variation that bypasses caching.

Result cache effectiveness can significantly reduce latency when applicable.

---

## Chunk SNOW-SLA-005

**metadata**

```yaml
chunk_id: SNOW-SLA-005
platform_id: snowflake
topic: sla
applies_to: [pipeline, scheduling]
severity: low
scenario_tags: [sla_breach, scheduling_delay]
signals: [delayed_start, upstream_dependency]
```

**content**
SLA breaches may occur due to delayed pipeline starts rather than slow execution.

Evidence:

* Queries start later than scheduled.
* Upstream dependencies complete late.
* No significant change in query execution time.

Actions:

* Review task and dependency scheduling.
* Validate upstream pipeline SLAs.
* Adjust scheduling windows to reflect realistic dependencies.

Scheduling delays should be addressed separately from query performance.

```
```
