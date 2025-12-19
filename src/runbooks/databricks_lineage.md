````md
# Databricks Lineage Impact Runbook

This runbook contains operational guidance for understanding and responding to
downstream impact when datasets or pipelines fail in Databricks environments.

---

## Chunk DBX-LIN-001
**metadata**
```yaml
chunk_id: DBX-LIN-001
platform_id: databricks
topic: lineage
applies_to: [dataset, job]
severity: high
scenario_tags: [blast_radius, downstream_impact]
signals: [dq_failure_upstream, lineage_edges_present]
````

**content**
When an upstream dataset fails data quality checks, use lineage to determine the
**blast radius** before taking action.

Steps:

1. Identify direct downstream datasets (depth = 1).
2. Identify secondary downstream consumers (depth = 2).
3. Prioritize downstream assets by criticality (dashboards, ML features, reports).

Response options:

* Block downstream publishing if incorrect data would cause harm.
* Allow downstream processing with warnings if consumers can tolerate degradation.
* Quarantine affected partitions for later correction.

Lineage should inform response severity, not dictate it blindly.

---

## Chunk DBX-LIN-002

**metadata**

```yaml
chunk_id: DBX-LIN-002
platform_id: databricks
topic: lineage
applies_to: [dataset]
severity: medium
scenario_tags: [lineage_confidence, inferred_edges]
signals: [low_confidence_edges, partial_telemetry]
```

**content**
Not all lineage edges have equal reliability.

Evidence:

* Some edges are inferred rather than directly observed.
* Observability gaps reduce confidence in inferred lineage.
* Edge confidence scores vary across datasets.

Guidance:

* Treat high-confidence edges as reliable indicators of dependency.
* Treat low-confidence edges as hypotheses requiring confirmation.
* Downgrade confidence during periods of degraded telemetry.

Explicitly communicate lineage confidence during incident response.

---

## Chunk DBX-LIN-003

**metadata**

```yaml
chunk_id: DBX-LIN-003
platform_id: databricks
topic: lineage
applies_to: [job, dataset]
severity: high
scenario_tags: [overwrite_risk, breaking_change]
signals: [write_mode_change, overwrite_operation]
```

**content**
Overwrite or destructive write operations can invalidate downstream assumptions.

Evidence:

* Write mode changes from append to overwrite.
* Downstream datasets show unexpected drops or resets.
* Historical partitions disappear unexpectedly.

Actions:

* Verify write modes before rerunning failed jobs.
* Use partition-level overwrites when possible.
* Communicate breaking changes to downstream consumers proactively.

Overwrite operations require heightened caution in shared environments.

---

## Chunk DBX-LIN-004

**metadata**

```yaml
chunk_id: DBX-LIN-004
platform_id: databricks
topic: lineage
applies_to: [dataset]
severity: medium
scenario_tags: [time_travel, recovery]
signals: [accidental_data_change, rollback_needed]
```

**content**
Delta Lake time travel can mitigate downstream impact after accidental data changes.

Use cases:

* Restore data after accidental overwrite.
* Compare current vs historical data for impact analysis.
* Validate whether downstream consumers read incorrect versions.

Guidance:

* Identify the last known-good version.
* Restore selectively where possible.
* Document rollback actions as separate recovery runs.

Time travel is a recovery tool, not a substitute for prevention.

---

## Chunk DBX-LIN-005

**metadata**

```yaml
chunk_id: DBX-LIN-005
platform_id: databricks
topic: lineage
applies_to: [dataset, governance]
severity: low
scenario_tags: [consumer_communication, incident_response]
signals: [downstream_alerts_needed]
```

**content**
Effective incident response includes clear communication to downstream consumers.

Recommendations:

* Notify consumers of affected datasets promptly.
* Include impact scope and confidence level.
* Provide guidance on whether to pause, refresh, or continue consumption.

Clear communication reduces downstream confusion and trust erosion.

```
```
