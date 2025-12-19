````md
# Snowflake Cost Optimization Runbook

This runbook contains operational guidance for diagnosing and remediating
Snowflake cost anomalies, with a focus on credit consumption, warehouse usage,
and inefficient query patterns.

---

## Chunk SNOW-COST-001
**metadata**
```yaml
chunk_id: SNOW-COST-001
platform_id: snowflake
topic: cost
applies_to: [warehouse]
severity: high
scenario_tags: [cost_spike, idle_warehouse]
signals: [credits_consumed, low_query_count]
````

**content**
A common cause of Snowflake cost spikes is warehouses consuming credits while idle.

Evidence:

* Credits consumed without corresponding query activity.
* Warehouses remain running during off-hours.
* Low query counts relative to warehouse uptime.

Actions:

* Enable auto-suspend with a short idle timeout.
* Enable auto-resume for usability.
* Review which workloads truly require always-on warehouses.

Idle warehouse costs are pure waste and should be eliminated first.

---

## Chunk SNOW-COST-002

**metadata**

```yaml
chunk_id: SNOW-COST-002
platform_id: snowflake
topic: cost
applies_to: [warehouse]
severity: high
scenario_tags: [cost_spike, overprovisioning]
signals: [credits_per_query_high, low_utilization]
```

**content**
Over-sized warehouses can dramatically increase credit usage without improving
query performance.

Evidence:

* High credits consumed per query.
* Query latency does not improve with larger warehouse size.
* CPU utilization remains low.

Actions:

* Downsize warehouses incrementally and remeasure.
* Use multiple smaller warehouses for isolated workloads.
* Align warehouse size with workload characteristics.

Bigger warehouses are not always faster or cheaper.

---

## Chunk SNOW-COST-003

**metadata**

```yaml
chunk_id: SNOW-COST-003
platform_id: snowflake
topic: cost
applies_to: [query]
severity: medium
scenario_tags: [cost_spike, inefficient_queries]
signals: [high_bytes_scanned, long_execution_time]
```

**content**
Inefficient queries can drive cost by scanning excessive data.

Evidence:

* High bytes scanned per query.
* Frequent full table scans.
* Queries lack selective filters.

Actions:

* Add selective predicates to reduce scanned data.
* Avoid `SELECT *` in large tables.
* Review query plans for pruning effectiveness.

Reducing scanned data directly reduces cost.

---

## Chunk SNOW-COST-004

**metadata**

```yaml
chunk_id: SNOW-COST-004
platform_id: snowflake
topic: cost
applies_to: [query]
severity: medium
scenario_tags: [cost_spike, cache_miss]
signals: [result_cache_miss, repeated_queries]
```

**content**
Repeated execution of identical queries that miss the result cache can inflate cost.

Evidence:

* Queries execute fully instead of returning cached results.
* Minor query text variations prevent cache hits.
* Session context differences invalidate caching.

Actions:

* Normalize query text where possible.
* Reuse sessions and roles consistently.
* Minimize unnecessary query variation.

Effective cache usage reduces both latency and cost.

---

## Chunk SNOW-COST-005

**metadata**

```yaml
chunk_id: SNOW-COST-005
platform_id: snowflake
topic: cost
applies_to: [account]
severity: low
scenario_tags: [cost_trend, growth]
signals: [gradual_credit_increase]
```

**content**
Gradual credit growth often reflects increasing data volumes or usage rather than
regressions.

Actions:

* Track credits per unit of data processed.
* Review retention and data lifecycle policies.
* Periodically reassess warehouse and workload alignment.

Cost trends should be reviewed proactively, not only during incidents.

```
```
