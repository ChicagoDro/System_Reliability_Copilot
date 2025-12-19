````md
# Databricks Observability Runbook

This runbook contains operational guidance for diagnosing and responding to
observability and telemetry issues in Databricks environments, with an emphasis
on OpenTelemetry-based signals.

---

## Chunk DBX-OBS-001
**metadata**
```yaml
chunk_id: DBX-OBS-001
platform_id: databricks
topic: observability
applies_to: [infrastructure, telemetry]
severity: high
scenario_tags: [otel_drop, missing_signals]
signals: [otel_exporter_failures, dropped_spans, dropped_logs]
````

**content**
If telemetry indicates exporter failures or dropped signals, treat the system as
**partially blind** until the telemetry pipeline is restored.

Evidence:

* Metrics show exporter send failures or queue overflow.
* Logs contain messages about dropped spans or logs.
* Sudden gaps appear in metrics, logs, or traces.

Actions:

1. Confirm exporter health and queue status.
2. Reduce backpressure by lowering signal volume or cardinality.
3. Adjust batching and queue sizes cautiously.
4. Temporarily reduce sampling rates if necessary.

While telemetry is degraded, rely more heavily on deterministic evidence
(run status, cost records, DQ results) for incident analysis.

---

## Chunk DBX-OBS-002

**metadata**

```yaml
chunk_id: DBX-OBS-002
platform_id: databricks
topic: observability
applies_to: [job, telemetry]
severity: medium
scenario_tags: [partial_telemetry, missing_spans]
signals: [logs_present_no_spans, spans_present_no_logs]
```

**content**
Partial telemetry can be misleading and should be interpreted carefully.

Evidence:

* Logs are present but spans are missing.
* Spans exist but lack associated logs.
* Trace or span IDs are missing from log records.

Actions:

* Verify trace context propagation in application code.
* Ensure collectors for logs and traces are both healthy.
* Confirm sampling policies retain error signals.

Avoid assuming healthy execution based solely on one signal type.

---

## Chunk DBX-OBS-003

**metadata**

```yaml
chunk_id: DBX-OBS-003
platform_id: databricks
topic: observability
applies_to: [telemetry]
severity: medium
scenario_tags: [high_cardinality, exporter_backpressure]
signals: [high_metric_cardinality, exporter_queue_full]
```

**content**
High-cardinality telemetry can overwhelm collectors and exporters.

Evidence:

* Exporter queues fill rapidly.
* Telemetry volume spikes without corresponding workload changes.
* Metrics include unbounded labels (user IDs, request IDs, file paths).

Actions:

* Remove or limit high-cardinality attributes.
* Aggregate metrics before export where possible.
* Prefer dimensional reduction over increasing queue sizes.

High-cardinality control is critical for observability reliability.

---

## Chunk DBX-OBS-004

**metadata**

```yaml
chunk_id: DBX-OBS-004
platform_id: databricks
topic: observability
applies_to: [job]
severity: low
scenario_tags: [log_volume, noise]
signals: [excessive_logs, low_signal_to_noise]
```

**content**
Excessive logging can degrade observability systems without improving insight.

Evidence:

* High log volume with repetitive messages.
* Important error messages buried in noise.
* Increased cost or latency in log pipelines.

Actions:

* Reduce log verbosity for non-error paths.
* Ensure errors and warnings are logged distinctly.
* Periodically review log content for usefulness.

Logging should prioritize clarity over completeness.

---

## Chunk DBX-OBS-005

**metadata**

```yaml
chunk_id: DBX-OBS-005
platform_id: databricks
topic: observability
applies_to: [telemetry, incident_response]
severity: medium
scenario_tags: [telemetry_uncertainty, incident_analysis]
signals: [signal_gaps, inconsistent_metrics]
```

**content**
When telemetry quality is uncertain, explicitly state confidence limitations in
incident analysis.

Guidance:

* Note periods of missing or degraded telemetry.
* Avoid definitive conclusions based on incomplete signals.
* Corroborate findings using independent evidence sources.

Operational decisions should account for telemetry confidence, not just content.

```
```
