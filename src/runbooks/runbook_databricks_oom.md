```markdown
---
## Chunk RB-DBX-001
**metadata**
```yaml
chunk_id: RB-DBX-001
platform_id: databricks
topic: memory_management
applies_to: [job, cluster]
severity: high
scenario_tags: [oom, exit_code_137, java_heap_space, container_killed]
signals: [ "java.lang.OutOfMemoryError", "Container killed by YARN", "Exit code 137" ]

```

**content**

### Mitigation: Handling OutOfMemory (OOM) / Exit Code 137

**Symptoms**

* Job fails with `Exit code 137`.
* Driver or Executor logs show `java.lang.OutOfMemoryError: Java heap space`.
* "Container killed by YARN for exceeding memory limits."

**Immediate Fixes (Triage)**

1. **Increase Cluster Memory:** Switch the `node_type_id` to a memory-optimized instance (e.g., from `r5.xlarge` to `r5.2xlarge` or `r5.4xlarge`).
2. **Turn on Autoscaling:** Ensure `autoscale` is enabled with a higher `max_workers` limit if the job is spilling to disk.
3. **Repartion Data:** If the error happens during a shuffle/join, the data might be skewed. Set `spark.sql.shuffle.partitions` to a higher value (e.g., `auto` or `2000`).

**Root Cause Analysis**

* Check the **Spark UI** > **Stages** tab for "Task Skew" (some tasks taking 10x longer than others).
* Check if a specific dataset has grown significantly in size recently (volume drift).

**Escalation**

* If resizing the cluster does not work, page the **Data Engineering** team (@data-eng).

---
