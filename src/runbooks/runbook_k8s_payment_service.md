```markdown
---
## Chunk RB-K8S-005
**metadata**
```yaml
chunk_id: RB-K8S-005
platform_id: k8s
topic: service_availability
applies_to: [service, deployment, pod]
severity: medium
scenario_tags: [connection_pool, database_timeout, crashloopbackoff]
signals: [ "Connection pool exhausted", "Health check failed", "500 Internal Server Error" ]

```

**content**

### Mitigation: Service Database Connection Exhaustion

**Symptoms**

* API returns `500 Internal Server Error`.
* Logs show `Connection pool exhausted` or `Waiting for connection`.
* Pods failing readiness probes (`/livez` or `/healthz`).

**Immediate Fixes**

1. **Rollback Deployment:** If this started after a new deploy, immediately rollback:
`kubectl rollout undo deployment/svc-payment-gateway`
2. **Scale Down Replicas:** Paradoxically, *too many* pods can saturate the DB connection limit. Reduce replica count temporarily if the DB CPU is 100%.
`kubectl scale deployment svc-payment-gateway --replicas=3`
3. **Check Database:** Verify the RDS/Postgres instance is running and not locked.

**Prevention**

* Ensure the application uses a connection pooler (e.g., PgBouncer).
* Review `MAX_POOL_SIZE` env var in the deployment yaml.

**Escalation**

* Page **Backend Team** (@backend-oncall) if rollback fails.

