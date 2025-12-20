-- sql/seed_reliability_data.sql
-- COMPLETE RELIABILITY DATASET (Performance + Cost + DQ + lineage)
-- v4.0 Final

PRAGMA foreign_keys = ON;

-- ============================================================================
-- 0. PLATFORMS & ENVIRONMENTS
-- ============================================================================
INSERT INTO platform (platform_id, platform_type, display_name, attributes_json) VALUES
('aws_prod', 'cloud', 'AWS Production', '{"region": "us-east-1"}'),
('databricks_prod', 'data', 'Databricks Premium', '{"workspace": "db-12345", "cloud": "aws", "tier": "premium"}'),
('snowflake_dw', 'warehouse', 'Snowflake Analytics', '{"account": "xy12345", "edition": "standard"}'),
('k8s_cluster', 'compute', 'EKS Cluster A', '{"version": "1.29", "cni": "vpc-cni"}'),
('airflow_prod', 'orchestrator', 'Airflow Production', '{"version": "2.8.1", "executor": "CeleryExecutor"}'),
('dbt_cloud', 'transform', 'dbt Cloud', '{"account": "dbt-99"}');

INSERT INTO environment (env_id, env_type, region, attributes_json, name) VALUES
('prod', 'production', 'us-east-1', '{}', 'Production'),
('stage', 'staging', 'us-west-2', '{}', 'Staging');

-- ============================================================================
-- 1. CONFIGURATIONS
-- ============================================================================
INSERT INTO compute_config (compute_config_id, platform_id, env_id, config_type, config_json, config_hash) VALUES
-- Databricks: Small Cluster (The cause of OOMs)
('cfg_dbx_small', 'databricks_prod', 'prod', 'job_cluster', 
 '{"driver_node_type_id": "i3.xlarge", "workers": 2, "spark_conf": {"spark.executor.memory": "4g", "spark.driver.memory": "4g"}}', 'hash_dbx_small'),
-- Databricks: Medium Cluster (For SLA/Reg Reporting)
('cfg_dbx_medium', 'databricks_prod', 'prod', 'job_cluster', 
 '{"driver_node_type_id": "i3.2xlarge", "workers": 4, "spark_conf": {"spark.executor.memory": "16g"}}', 'hash_dbx_med'),
-- K8s: Strict Memory Limit (The cause of CrashLoopBackOff)
('cfg_k8s_pay_api', 'k8s_cluster', 'prod', 'deployment_spec', 
 '{"resources": {"limits": {"memory": "512Mi", "cpu": "500m"}}, "replicas": 3}', 'hash_k8s_pay'),
-- K8s: Low CPU Limit (The cause of Latency)
('cfg_k8s_nginx', 'k8s_cluster', 'prod', 'deployment_spec', 
 '{"replicas": 2, "resources": {"limits": {"cpu": "200m"}}}', 'hash_k8s_nginx');

-- ============================================================================
-- 2. RESOURCES
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, is_active) VALUES
('res_job_nightly_fact', 'databricks_prod', 'prod', 'job', 'job-555', 'nightly_fact_aggregation', 'finance_data', 'data_eng', '{"priority": "critical", "cost_center": "finance-101"}', 1),
('res_job_silver_gold', 'databricks_prod', 'prod', 'job', 'job-777', 'silver_to_gold_merge', 'core_banking', 'analytics_eng', '{"priority": "high"}', 1),
('res_job_reg_report', 'databricks_prod', 'prod', 'job', 'job-reg-001', 'monthly_regulatory_report', 'compliance', 'compliance_team', '{"sla_runtime_mins": 30, "priority": "p0"}', 1),
('res_tbl_customers', 'snowflake_dw', 'prod', 'table', 'db.public.customers', 'customers_master', 'analytics', 'analytics_eng', '{"retention_days": 1}', 1),
('res_af_vendor_dag', 'airflow_prod', 'prod', 'dag', 'dag_vendor_ingest', 'vendor_ingest_daily', 'ingestion', 'data_eng', '{}', 1),
('res_dbt_kpis', 'dbt_cloud', 'prod', 'model', 'model.fct_monthly_kpis', 'fct_monthly_kpis', 'finance', 'analytics_team', '{}', 1),
('res_svc_payments', 'k8s_cluster', 'prod', 'service', 'svc-pay-99', 'payment_gateway_api', 'payments', 'backend_team', '{}', 1),
('res_api_backend', 'k8s_cluster', 'prod', 'service', 'svc-api-01', 'checkout-api', 'backend', 'backend_team', '{}', 1),
('res_web_nginx', 'k8s_cluster', 'prod', 'service', 'svc-nginx-01', 'frontend-nginx', 'web', 'frontend_team', '{}', 1),
('res_noisy_app', 'k8s_cluster', 'prod', 'pod', 'pod-noisy-001', 'noisy-logger-v1', 'default', 'dev_team', '{}', 1),
('res_db_postgres', 'aws_prod', 'prod', 'database', 'db-rds-009', 'users_db_primary', 'rds', 'dba_team', '{}', 1);

-- ============================================================================
-- 3. LINEAGE
-- ============================================================================
INSERT INTO lineage_edge (edge_id, env_id, src_resource_id, dst_resource_id, relation_type) VALUES
('edge_1', 'prod', 'res_af_vendor_dag', 'res_dbt_kpis', 'TRIGGERS'),
('edge_2', 'prod', 'res_dbt_kpis', 'res_job_reg_report', 'FEEDS'),
('edge_3', 'prod', 'res_svc_payments', 'res_db_postgres', 'CONNECTS_TO'),
('edge_4', 'prod', 'res_api_backend', 'res_svc_payments', 'CALLS'),
('edge_5', 'prod', 'res_web_nginx', 'res_api_backend', 'CALLS');

-- ============================================================================
-- 4. SCENARIOS
-- ============================================================================

-- --- SCENARIO 1: Databricks OOM (High Cost Impact) ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, compute_config_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_fact_100', 'databricks_prod', 'prod', 'res_job_nightly_fact', 'cfg_dbx_small', 'run-abc-99', 'batch', 'SUCCESS', datetime('now', '-26 hours'), datetime('now', '-25 hours'), 'Succeeded'),
('run_fact_101', 'databricks_prod', 'prod', 'res_job_nightly_fact', 'cfg_dbx_small', 'run-abc-101', 'batch', 'FAILED', datetime('now', '-3 hours'), datetime('now', '-2 hours'), 'Job failed with exit code 137');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_fact_01', 'WARN', 'Executor 15 lost heartbeat. Block manager scrambling.', 'res_job_nightly_fact', 'run_fact_101', datetime('now', '-2 hours', '-30 minutes')),
('log_fact_02', 'ERROR', 'java.lang.OutOfMemoryError: Java heap space. Container killed by YARN for exceeding memory limits. Exit code 137.', 'res_job_nightly_fact', 'run_fact_101', datetime('now', '-2 hours', '-10 minutes'));

INSERT INTO metric_point (metric_point_id, resource_id, run_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_jvm_01', 'res_job_nightly_fact', 'run_fact_101', 'jvm_heap_usage', 'gauge', 'mb', 3800, datetime('now', '-2 hours', '-30 minutes')),
('met_jvm_02', 'res_job_nightly_fact', 'run_fact_101', 'jvm_heap_usage', 'gauge', 'mb', 4150, datetime('now', '-2 hours', '-15 minutes'));

-- NEW: Cost Spikes for this OOM Run
-- Shows that the failed run still cost money (Waste)
INSERT INTO metric_point (metric_point_id, resource_id, run_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_cost_oom_1', 'res_job_nightly_fact', 'run_fact_101', 'run_cost_usd', 'gauge', 'usd', 45.50, datetime('now', '-2 hours'));


-- --- SCENARIO 2: K8s Service Crash ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, compute_config_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_deploy_v45', 'k8s_cluster', 'prod', 'res_svc_payments', 'cfg_k8s_pay_api', 'deploy-v45', 'deploy', 'FAILED', datetime('now', '-5 hours'), datetime('now', '-4 hours'), 'OOMKilled');

INSERT INTO metric_point (metric_point_id, resource_id, run_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_k8s_mem_01', 'res_svc_payments', 'run_deploy_v45', 'container_memory_usage_bytes', 'gauge', 'mb', 540, datetime('now', '-4 hours', '-5 minutes'));

-- --- SCENARIO 3: Snowflake Data Loss ---
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_row_01', 'res_tbl_customers', 'row_count', 'gauge', 'count', 10500, datetime('now', '-3 days')),
('met_row_04', 'res_tbl_customers', 'row_count', 'gauge', 'count', 0, datetime('now', '-1 hour'));

INSERT INTO log_record (log_id, severity_text, body, resource_id, time) VALUES
('log_sf_01', 'INFO', 'DROP TABLE customers_master;', 'res_tbl_customers', datetime('now', '-2 days')),
('log_sf_02', 'ERROR', 'Failure using UNDROP TABLE. Time Travel data is not available... retention period (1 day).', 'res_tbl_customers', datetime('now', '-10 hours'));

-- --- SCENARIO 4: Airflow Failure ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_af_daily_001', 'airflow_prod', 'prod', 'res_af_vendor_dag', 'run_2025_12_18', 'scheduled', 'FAILED', datetime('now', '-8 hours'), datetime('now', '-7 hours'), 'DQ Validation Failed');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_af_01', 'ERROR', 'DQ Rule Failed: row_count > 0. Actual: 0.', 'res_af_vendor_dag', 'run_af_daily_001', datetime('now', '-7 hours', '-5 minutes'));

-- --- SCENARIO 5: Schema Drift ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_dbx_drift_001', 'databricks_prod', 'prod', 'res_job_silver_gold', 'run-drift-99', 'batch', 'FAILED', datetime('now', '-30 minutes'), datetime('now'), 'AnalysisException: cannot resolve column');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_drift_02', 'ERROR', 'pyspark.sql.utils.AnalysisException: cannot resolve "user_id" given input columns...', 'res_job_silver_gold', 'run_dbx_drift_001', datetime('now', '-20 minutes'));

-- --- SCENARIO 6: dbt Duplicates (DQ Anomaly) ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_dbt_fail_99', 'dbt_cloud', 'prod', 'res_dbt_kpis', 'dbt-run-4421', 'build', 'FAILED', datetime('now', '-1 day'), datetime('now', '-23 hours'), 'Tests failed');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_dbt_02', 'ERROR', 'Failure in test unique_fct_monthly_kpis_id. Got 5 failing rows.', 'res_dbt_kpis', 'run_dbt_fail_99', datetime('now', '-23 hours', '-5 minutes'));

-- NEW: Data Quality Metrics
-- Showing Output > Input, which mathematically proves duplication happened
INSERT INTO metric_point (metric_point_id, resource_id, run_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_dbt_in', 'res_dbt_kpis', 'run_dbt_fail_99', 'row_count_input', 'gauge', 'count', 50000, datetime('now', '-23 hours', '-10 minutes')),
('met_dbt_out', 'res_dbt_kpis', 'run_dbt_fail_99', 'row_count_output', 'gauge', 'count', 50005, datetime('now', '-23 hours', '-5 minutes')); -- 5 duplicates


-- --- SCENARIO 7: SLA Breach (Regulatory Report) ---
WITH RECURSIVE runs(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM runs WHERE x<20)
INSERT INTO run (run_id, platform_id, env_id, resource_id, compute_config_id, run_type, status, started_at, ended_at, message)
SELECT 
    'run_reg_' || x, 
    'databricks_prod', 
    'prod', 
    'res_job_reg_report', 
    'cfg_dbx_medium',
    'batch', 
    'SUCCESS', 
    datetime('now', '-' || (21-x) || ' days'), 
    CASE WHEN x < 15 THEN datetime('now', '-' || (21-x) || ' days', '+25 minutes')
         ELSE datetime('now', '-' || (21-x) || ' days', '+45 minutes') END,
    CASE WHEN x < 15 THEN 'Succeeded' ELSE 'Succeeded (Slow)' END
FROM runs;

WITH RECURSIVE runs(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM runs WHERE x<20)
INSERT INTO metric_point (metric_point_id, resource_id, run_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_vol_' || x, 'res_job_reg_report', 'run_reg_' || x, 'input_record_count', 'gauge', 'count',
    CASE WHEN x < 15 THEN 2000000 ELSE 25000000 END,
    datetime('now', '-' || (21-x) || ' days')
FROM runs;

-- --- SCENARIO 8: Cost Overview (30 Days) ---
-- Standard Daily Cost
WITH RECURSIVE dates(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM dates WHERE x<30)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'cost_dbx_' || x, 'res_job_nightly_fact', 'daily_cost', 'gauge', 'usd', 
    100.00 + ((30-x) * 2.5), datetime('now', '-' || x || ' days')
FROM dates;

-- NEW: DBU Usage (Unit Efficiency)
-- Shows if cost went up because price changed or because we used more compute
WITH RECURSIVE dates(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM dates WHERE x<30)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'dbu_dbx_' || x, 'res_job_nightly_fact', 'dbu_usage_total', 'gauge', 'dbu', 
    50 + ((30-x) * 1.5), datetime('now', '-' || x || ' days')
FROM dates;

-- --- SCENARIO 9: Web/Black Friday Latency ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, compute_config_id, run_type, status, started_at, ended_at, message) VALUES
('deploy_api_v40', 'k8s_cluster', 'prod', 'res_api_backend', 'cfg_k8s_nginx', 'deploy', 'SUCCESS', datetime('now', '-24 hours'), datetime('now', '-23 hours', '-50 minutes'), 'Active');

-- 1. LATENCY
WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_lat_api_' || x, 'res_api_backend', 'latency_p95', 'gauge', 'ms', 
    CASE WHEN x < 4 THEN 2500 ELSE 45 END, datetime('now', '-' || x || ' hours')
FROM hours;

-- 2. SATURATION (CPU)
WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_cpu_api_' || x, 'res_api_backend', 'container_cpu_usage_seconds_total', 'gauge', 'cores', 
    CASE WHEN x < 4 THEN 0.2 ELSE 0.02 END, datetime('now', '-' || x || ' hours')
FROM hours;

-- 3. TRAFFIC (Demand)
WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_rps_api_' || x, 'res_api_backend', 'http_requests_per_second', 'gauge', 'rps', 
    CASE WHEN x < 4 THEN 2000 ELSE 100 END, datetime('now', '-' || x || ' hours')
FROM hours;

-- 4. ERRORS (Health)
WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_err_api_' || x, 'res_api_backend', 'http_error_rate_5xx', 'gauge', 'count', 
    CASE WHEN x < 4 THEN 50 ELSE 0 END, datetime('now', '-' || x || ' hours')
FROM hours;

-- 5. SCALING (Replica Count) - NEW
-- Shows if autoscaling kicked in (or got stuck)
WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_replicas_api_' || x, 'res_api_backend', 'pod_replica_count', 'gauge', 'count', 
    2, -- Stuck at 2 replicas despite high load (shows config limit issue)
    datetime('now', '-' || x || ' hours')
FROM hours;


-- --- SCENARIO 10: Noisy Logs ---
WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x<50)
INSERT INTO log_record (log_id, severity_text, body, resource_id, time)
SELECT 'log_noise_' || x, 'WARN', 'DeprecationWarning: The "imp" module is deprecated...', 'res_noisy_app', datetime('now', '-' || x || ' minutes')
FROM cnt;

-- ============================================================================
-- 5. INCIDENTS
-- ============================================================================
INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, summary, attributes_json) VALUES
('inc_001', 'prod', 'Nightly Fact Job OOM', 'HIGH', 'OPEN', datetime('now', '-2 hours'), 'Job failed OOM. Config limit is 4GB.', '{"related_resource_id": "res_job_nightly_fact"}'),
('inc_002', 'prod', 'Payment Gateway CrashLoopBackOff', 'MEDIUM', 'RESOLVED', datetime('now', '-5 hours'), 'Pod restarting. Exit Code 137 (OOM).', '{"related_resource_id": "res_svc_payments"}'),
('inc_003', 'prod', 'Customer Master Table Empty', 'CRITICAL', 'OPEN', datetime('now', '-1 hour'), 'Automated checks detected 0 rows.', '{"related_resource_id": "res_tbl_customers"}'),
('inc_004', 'prod', 'Vendor Ingestion Empty File', 'MEDIUM', 'OPEN', datetime('now', '-7 hours'), 'Daily vendor file arrived but was empty.', '{"related_resource_id": "res_af_vendor_dag"}'),
('inc_005', 'prod', 'Silver/Gold Schema Mismatch', 'HIGH', 'OPEN', datetime('now', '-20 minutes'), 'Job aborted due to missing column "user_id".', '{"related_resource_id": "res_job_silver_gold"}'),
('inc_006', 'prod', 'KPI Model Duplicates', 'LOW', 'RESOLVED', datetime('now', '-23 hours'), 'Primary key violation in monthly KPIs.', '{"related_resource_id": "res_dbt_kpis"}'),
('inc_infra_001', 'prod', 'High Latency on Checkout API', 'HIGH', 'OPEN', datetime('now', '-2 hours'), 'P95 Latency > 2s. Traffic spike exceeds replica capacity.', '{"service": "res_api_backend"}');

-- ============================================================================
-- 6. INCIDENT <-> RESOURCE LINKS
-- ============================================================================
INSERT INTO incident_resource (incident_id, resource_id, relation) VALUES
('inc_001', 'res_job_nightly_fact', 'AFFECTS'),
('inc_002', 'res_svc_payments', 'AFFECTS'),
('inc_003', 'res_tbl_customers', 'AFFECTS'),
('inc_004', 'res_af_vendor_dag', 'AFFECTS'),
('inc_005', 'res_job_silver_gold', 'AFFECTS'),
('inc_006', 'res_dbt_kpis', 'AFFECTS'),
('inc_infra_001', 'res_api_backend', 'AFFECTS');