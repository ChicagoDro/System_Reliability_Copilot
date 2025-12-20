-- sql/seed_reliability_data.sql
-- UNIFIED MASTER DATASET
-- Scenarios:
-- 1. Databricks: Nightly Fact Job OOM (Java Heap Space)
-- 2. K8s: Payment Service Crash (Connection Pool Exhaustion)
-- 3. Snowflake: Customer Table Data Loss (0 Rows)
-- 4. Airflow: Vendor Ingestion Failure (Empty Input File)
-- 5. Databricks: Silver-to-Gold Schema Drift (Missing Column)
-- 6. dbt: KPI Model Failure (Primary Key Duplication)
-- 7. Databricks: SLA Breach (Regulatory Report)
-- 8. Cost: Creeping Cloud Bill
-- 9. K8s/Web: "Black Friday" Latency Spike (Nginx/API)

PRAGMA foreign_keys = ON;

-- ============================================================================
-- 0. PLATFORMS & ENVIRONMENTS
-- ============================================================================

INSERT INTO platform (platform_id, platform_type, display_name, attributes_json) VALUES
('aws_prod', 'cloud', 'AWS Production', '{"region": "us-east-1"}'),
('databricks_prod', 'data', 'Databricks Premium', '{"workspace": "db-12345", "cloud": "aws"}'),
('snowflake_dw', 'warehouse', 'Snowflake Analytics', '{"account": "xy12345", "edition": "enterprise"}'),
('k8s_cluster', 'compute', 'EKS Cluster A', '{"version": "1.28"}'),
('airflow_prod', 'orchestrator', 'Airflow Production', '{"version": "2.8.1"}'),
('dbt_cloud', 'transform', 'dbt Cloud', '{"account": "dbt-99"}');

INSERT INTO environment (env_id, env_type, region, attributes_json, name) VALUES
('prod', 'production', 'us-east-1', '{}', 'Production'),
('stage', 'staging', 'us-west-2', '{}', 'Staging');

-- ============================================================================
-- SCENARIO 1: Databricks OOM (The Classic)
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, created_at, is_active) VALUES
('res_job_nightly_fact', 'databricks_prod', 'prod', 'job', 'job-555', 'nightly_fact_aggregation', 'finance_data', 'data_eng', '{"priority": "critical", "sla": "06:00 UTC"}', datetime('now', '-90 days'), 1);

INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, attempt, started_at, ended_at, message) VALUES
('run_fact_100', 'databricks_prod', 'prod', 'res_job_nightly_fact', 'run-abc-99', 'batch', 'SUCCESS', 1, datetime('now', '-26 hours'), datetime('now', '-25 hours'), 'Succeeded'),
('run_fact_101', 'databricks_prod', 'prod', 'res_job_nightly_fact', 'run-abc-100', 'batch', 'FAILED', 1, datetime('now', '-3 hours'), datetime('now', '-2 hours'), 'Job failed with exit code 137');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_fact_01', 'WARN', 'Executor 15 lost heartbeat. Block manager scrambling.', 'res_job_nightly_fact', 'run_fact_101', datetime('now', '-2 hours', '-30 minutes')),
('log_fact_02', 'ERROR', 'java.lang.OutOfMemoryError: Java heap space. Container killed by YARN for exceeding memory limits. Exit code 137.', 'res_job_nightly_fact', 'run_fact_101', datetime('now', '-2 hours', '-10 minutes'));

INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, summary, attributes_json) VALUES
('inc_001', 'prod', 'Nightly Fact Job OOM', 'HIGH', 'OPEN', datetime('now', '-2 hours'), 'The nightly finance aggregation failed with OOM errors.', '{"related_resource_id": "res_job_nightly_fact"}');

-- ============================================================================
-- SCENARIO 2: K8s Service Crash (Connection Pool)
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, created_at, is_active) VALUES
('res_svc_payments', 'k8s_cluster', 'prod', 'service', 'svc-pay-99', 'payment_gateway_api', 'payments', 'backend_team', datetime('now', '-1 year'), 1);

INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_deploy_v45', 'k8s_cluster', 'prod', 'res_svc_payments', 'deploy-v45', 'deploy', 'FAILED', datetime('now', '-5 hours'), datetime('now', '-4 hours'), 'Health check timeout');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_pay_01', 'WARN', 'Connection pool exhausted. Waiting for connection...', 'res_svc_payments', 'run_deploy_v45', datetime('now', '-4 hours', '-30 minutes')),
('log_pay_02', 'ERROR', 'FATAL: Health check /livez failed. Database unavailable. Rolling back.', 'res_svc_payments', 'run_deploy_v45', datetime('now', '-4 hours', '-10 minutes'));

INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, closed_at, summary, attributes_json) VALUES
('inc_002', 'prod', 'Payment Gateway Deployment Failed', 'MEDIUM', 'RESOLVED', datetime('now', '-5 hours'), datetime('now', '-1 hour'), 'Deployment v45 failed due to DB connection saturation.', '{"related_resource_id": "res_svc_payments"}');

-- ============================================================================
-- SCENARIO 3: Snowflake Data Loss (0 Rows)
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, created_at, is_active) VALUES
('res_tbl_customers', 'snowflake_dw', 'prod', 'table', 'db.public.customers', 'customers_master', 'analytics', 'analytics_eng', datetime('now', '-6 months'), 1);

INSERT INTO metric_point (metric_point_id, metric_name, metric_type, unit, value_number, resource_id, time) VALUES
('met_row_01', 'row_count', 'gauge', 'count', 10500, 'res_tbl_customers', datetime('now', '-2 days')),
('met_row_02', 'row_count', 'gauge', 'count', 0, 'res_tbl_customers', datetime('now', '-12 hours'));

INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, summary, attributes_json) VALUES
('inc_003', 'prod', 'Customer Master Table Empty', 'CRITICAL', 'OPEN', datetime('now', '-10 hours'), 'Automated checks detected 0 rows in the customer master table.', '{"related_resource_id": "res_tbl_customers"}');

-- ============================================================================
-- SCENARIO 4: Airflow Ingestion Failure (Empty File)
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, created_at, is_active) VALUES
('res_af_vendor_dag', 'airflow_prod', 'prod', 'dag', 'dag_vendor_ingest', 'vendor_ingest_daily', 'ingestion', 'data_eng', datetime('now', '-1 year'), 1);

INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_af_daily_001', 'airflow_prod', 'prod', 'res_af_vendor_dag', 'run_2025_12_18', 'scheduled', 'FAILED', datetime('now', '-8 hours'), datetime('now', '-7 hours'), 'DQ Validation Failed');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_af_01', 'INFO', 'Downloading vendor_data_20251218.csv from SFTP...', 'res_af_vendor_dag', 'run_af_daily_001', datetime('now', '-7 hours', '-10 minutes')),
('log_af_02', 'WARN', 'File size is 0 bytes.', 'res_af_vendor_dag', 'run_af_daily_001', datetime('now', '-7 hours', '-9 minutes')),
('log_af_03', 'ERROR', 'DQ Rule Failed: row_count > 0. Actual: 0.', 'res_af_vendor_dag', 'run_af_daily_001', datetime('now', '-7 hours', '-5 minutes'));

INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, summary, attributes_json) VALUES
('inc_004', 'prod', 'Vendor Ingestion Empty File', 'MEDIUM', 'OPEN', datetime('now', '-7 hours'), 'Daily vendor file arrived but was empty.', '{"related_resource_id": "res_af_vendor_dag"}');

-- ============================================================================
-- SCENARIO 5: Databricks Schema Drift (Missing Column)
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, created_at, is_active) VALUES
('res_job_silver_gold', 'databricks_prod', 'prod', 'job', 'job-777', 'silver_to_gold_merge', 'core_banking', 'analytics_eng', datetime('now', '-60 days'), 1);

INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_dbx_drift_001', 'databricks_prod', 'prod', 'res_job_silver_gold', 'run-drift-99', 'batch', 'FAILED', datetime('now', '-30 minutes'), datetime('now'), 'AnalysisException: cannot resolve column');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_drift_01', 'INFO', 'Starting Merge to Gold...', 'res_job_silver_gold', 'run_dbx_drift_001', datetime('now', '-25 minutes')),
('log_drift_02', 'ERROR', 'pyspark.sql.utils.AnalysisException: cannot resolve "user_id" given input columns: [transaction_id, amt, timestamp]', 'res_job_silver_gold', 'run_dbx_drift_001', datetime('now', '-20 minutes'));

INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, summary, attributes_json) VALUES
('inc_005', 'prod', 'Silver/Gold Schema Mismatch', 'HIGH', 'OPEN', datetime('now', '-20 minutes'), 'Job aborted due to missing column "user_id" in upstream data.', '{"related_resource_id": "res_job_silver_gold"}');

-- ============================================================================
-- SCENARIO 6: dbt Business Logic Failure (Duplicates)
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, created_at, is_active) VALUES
('res_dbt_kpis', 'dbt_cloud', 'prod', 'model', 'model.fct_monthly_kpis', 'fct_monthly_kpis', 'finance', 'analytics_team', datetime('now', '-2 years'), 1);

INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_dbt_fail_99', 'dbt_cloud', 'prod', 'res_dbt_kpis', 'dbt-run-4421', 'build', 'FAILED', datetime('now', '-1 day'), datetime('now', '-23 hours'), 'Tests failed');

INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time) VALUES
('log_dbt_01', 'INFO', 'Start test unique_fct_monthly_kpis_id', 'res_dbt_kpis', 'run_dbt_fail_99', datetime('now', '-23 hours', '-10 minutes')),
('log_dbt_02', 'ERROR', 'Failure in test unique_fct_monthly_kpis_id. Got 5 failing rows.', 'res_dbt_kpis', 'run_dbt_fail_99', datetime('now', '-23 hours', '-5 minutes'));

INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, closed_at, summary, attributes_json) VALUES
('inc_006', 'prod', 'KPI Model Duplicates', 'LOW', 'RESOLVED', datetime('now', '-23 hours'), datetime('now', '-20 hours'), 'Primary key violation in monthly KPIs.', '{"related_resource_id": "res_dbt_kpis"}');

-- ============================================================================
-- SCENARIO 7: SLA Breach (Regulatory Report)
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, created_at, is_active) VALUES
('res_job_reg_report', 'databricks_prod', 'prod', 'job', 'job-reg-001', 'monthly_regulatory_report', 'compliance', 'compliance_team', '{"sla_runtime_mins": 30, "priority": "p0"}', datetime('now', '-1 year'), 1);

INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_reg_good', 'databricks_prod', 'prod', 'res_job_reg_report', 'run-reg-001', 'batch', 'SUCCESS', datetime('now', '-25 hours'), datetime('now', '-24 hours', '-40 minutes'), 'Succeeded'),
('run_reg_bad', 'databricks_prod', 'prod', 'res_job_reg_report', 'run-reg-002', 'batch', 'SUCCESS', datetime('now', '-60 minutes'), datetime('now', '-10 minutes'), 'Succeeded but slow');

-- ============================================================================
-- SCENARIO 8: Cost Anomalies (The "Creeping" Bill)
-- ============================================================================
-- 1. Stable Cost: The K8s Cluster (Fixed size)
WITH RECURSIVE dates(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM dates WHERE x<30)
INSERT INTO metric_point (metric_point_id, metric_name, metric_type, unit, value_number, resource_id, time)
SELECT 
    'cost_k8s_' || x, 
    'daily_cost', 
    'gauge', 
    'usd', 
    50.00, 
    'res_svc_payments', 
    datetime('now', '-' || x || ' days')
FROM dates;

-- 2. Rising Cost: The Nightly Fact Job (Databricks)
WITH RECURSIVE dates(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM dates WHERE x<30)
INSERT INTO metric_point (metric_point_id, metric_name, metric_type, unit, value_number, resource_id, time)
SELECT 
    'cost_dbx_' || x, 
    'daily_cost', 
    'gauge', 
    'usd', 
    100.00 + ((30-x) * 5.0), -- Increases by $5 every day recent
    'res_job_nightly_fact', 
    datetime('now', '-' || x || ' days')
FROM dates;

-- 3. Spiky Cost: The Silver-to-Gold Job (Retry Storm)
WITH RECURSIVE dates(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM dates WHERE x<30)
INSERT INTO metric_point (metric_point_id, metric_name, metric_type, unit, value_number, resource_id, time)
SELECT 
    'cost_silver_' || x, 
    'daily_cost', 
    'gauge', 
    'usd', 
    CASE WHEN x = 1 THEN 150.00 ELSE 20.00 END, 
    'res_job_silver_gold', 
    datetime('now', '-' || x || ' days')
FROM dates;

-- ============================================================================
-- SCENARIO 9: Web/K8s Latency (Black Friday)
-- ============================================================================

-- 1. Resources (Added external_id to prevent unique constraint crash)
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, is_active) VALUES
('res_web_nginx', 'k8s_cluster', 'prod', 'service', 'svc-nginx-01', 'frontend-nginx', 'web', 'frontend_team', 1),
('res_api_backend', 'k8s_cluster', 'prod', 'service', 'svc-api-01', 'checkout-api', 'backend', 'backend_team', 1),
('res_db_postgres', 'aws_prod', 'prod', 'database', 'db-rds-009', 'users_db_primary', 'rds', 'dba_team', 1);

-- 2. "Runs" (Representing Deployments)
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('deploy_api_v40', 'k8s_cluster', 'prod', 'res_api_backend', 'deploy-v40-1', 'deploy', 'SUCCESS', datetime('now', '-24 hours'), datetime('now', '-23 hours', '-50 minutes'), 'Deployed v40.1');

-- 3. Metrics (The "Golden Signals")
-- Latency spikes from 45ms (normal) to 2500ms (incident) on the API
WITH RECURSIVE hours(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM hours WHERE x<10)
INSERT INTO metric_point (metric_point_id, metric_name, metric_type, unit, value_number, resource_id, time)
SELECT 
    'met_lat_' || x, 
    'latency_p95', 
    'gauge', 
    'ms', 
    CASE WHEN x < 3 THEN 2500 ELSE 45 END, -- Recent spike in the last 2 hours
    'res_api_backend', 
    datetime('now', '-' || x || ' hours')
FROM hours;

-- 4. Incident (The Result)
INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, summary, attributes_json) VALUES
('inc_infra_001', 'prod', 'High Latency on Checkout API', 'HIGH', 'OPEN', datetime('now', '-2 hours'), 'P95 Latency > 2s. Checkout flow blocked.', '{"service": "res_api_backend"}');

-- OPTIONAL: Add "Spam" logs to demonstrate noise reduction
-- 1. Create the Resource (The Noisy App)
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, created_at, is_active) VALUES
('res_noisy_app', 'k8s_cluster', 'prod', 'pod', 'pod-noisy-001', 'noisy-logger-v1', 'default', 'dev_team', datetime('now', '-30 days'), 1);

-- 2. Create a "Daemon" Run (The FK Anchor)
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_noise_daemon', 'k8s_cluster', 'prod', 'res_noisy_app', 'daemon-1', 'service', 'RUNNING', datetime('now', '-1 day'), NULL, 'Always-on logging service');

-- 3. Insert 50 repetitive warning logs
WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x<50)
INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time)
SELECT 
    'log_noise_' || x, 
    'WARN', 
    'DeprecationWarning: The "imp" module is deprecated in favor of "importlib".', 
    'res_noisy_app', 
    'run_noise_daemon',
    datetime('now', '-' || x || ' minutes')
FROM cnt;