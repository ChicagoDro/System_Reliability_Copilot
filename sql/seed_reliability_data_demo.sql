-- sql/seed_reliability_data_demo.sql
-- RICH DEMO DATASET: 3 Scenarios (ETL Failure, API Latency, Data Quality Breach)

-- 1. Platforms
INSERT INTO platform (platform_id, platform_type, display_name, attributes_json) VALUES
('aws_prod', 'cloud', 'AWS Production', '{"region": "us-east-1"}'),
('databricks_prod', 'data', 'Databricks Premium', '{"workspace": "db-12345", "cloud": "aws"}'),
('snowflake_dw', 'warehouse', 'Snowflake Analytics', '{"account": "xy12345", "edition": "enterprise"}'),
('k8s_cluster', 'compute', 'EKS Cluster A', '{"version": "1.28"}');

-- 2. Environments
INSERT INTO environment (env_id, env_type, region, attributes_json, name) VALUES
('prod', 'production', 'us-east-1', '{}', 'Production'),
('stage', 'staging', 'us-west-2', '{}', 'Staging');

-- ------------------------------------------------------------------------------------------------
-- SCENARIO 1: The "OOM" Crash (Databricks Job)
-- ------------------------------------------------------------------------------------------------

-- Resource: The Nightly Fact Job
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, created_at, is_active) VALUES
('res_job_nightly_fact', 'databricks_prod', 'prod', 'job', 'job-555', 'nightly_fact_aggregation', 'finance_data', 'data_eng_team', '{"priority": "critical", "sla": "06:00 UTC"}', datetime('now', '-90 days'), 1);

-- Runs: It failed 2 hours ago
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, attempt, started_at, ended_at, message, attributes_json) VALUES
('run_fact_100', 'databricks_prod', 'prod', 'res_job_nightly_fact', 'run-abc-99', 'batch', 'SUCCESS', 1, datetime('now', '-26 hours'), datetime('now', '-25 hours'), 'Succeeded', '{}'),
('run_fact_101', 'databricks_prod', 'prod', 'res_job_nightly_fact', 'run-abc-100', 'batch', 'FAILED', 1, datetime('now', '-3 hours'), datetime('now', '-2 hours'), 'Job failed with exit code 137', '{"trigger": "schedule"}');

-- Logs: The smoking gun (Out Of Memory)
INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time, attributes_json) VALUES
('log_fact_01', 'INFO', 'Starting shuffle for 5TB dataset...', 'res_job_nightly_fact', 'run_fact_101', datetime('now', '-2 hours', '-50 minutes'), '{}'),
('log_fact_02', 'WARN', 'Executor 15 lost heartbeat. Block manager scrambling.', 'res_job_nightly_fact', 'run_fact_101', datetime('now', '-2 hours', '-30 minutes'), '{}'),
('log_fact_03', 'ERROR', 'java.lang.OutOfMemoryError: Java heap space. Container killed by YARN for exceeding memory limits. Exit code 137.', 'res_job_nightly_fact', 'run_fact_101', datetime('now', '-2 hours', '-10 minutes'), '{}');

-- Incident: The ticket opened because of the failure
INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, closed_at, summary, attributes_json) VALUES
('inc_001', 'prod', 'Nightly Fact Job OOM', 'HIGH', 'OPEN', datetime('now', '-2 hours'), NULL, 'The nightly finance aggregation failed with OOM errors. SLA is at risk.', '{"related_resource_id": "res_job_nightly_fact", "related_run_id": "run_fact_101"}');


-- ------------------------------------------------------------------------------------------------
-- SCENARIO 2: The "Bad Deploy" (API Service)
-- ------------------------------------------------------------------------------------------------

-- Resource: Payment Service
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, created_at, is_active) VALUES
('res_svc_payments', 'k8s_cluster', 'prod', 'service', 'svc-pay-99', 'payment_gateway_api', 'payments', 'backend_team', '{"tier": "1"}', datetime('now', '-1 year'), 1);

-- Runs: Deployment history
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, attempt, started_at, ended_at, message, attributes_json) VALUES
('run_deploy_v44', 'k8s_cluster', 'prod', 'res_svc_payments', 'deploy-v44', 'deploy', 'SUCCESS', 1, datetime('now', '-7 days'), datetime('now', '-7 days'), 'Deployed v44', '{}'),
('run_deploy_v45', 'k8s_cluster', 'prod', 'res_svc_payments', 'deploy-v45', 'deploy', 'FAILED', 1, datetime('now', '-5 hours'), datetime('now', '-4 hours'), 'Health check timeout', '{}');

-- Logs: Connection Pool exhaustion
INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time, attributes_json) VALUES
('log_pay_01', 'INFO', 'Initializing DB connection pool (max=50)...', 'res_svc_payments', 'run_deploy_v45', datetime('now', '-4 hours', '-55 minutes'), '{}'),
('log_pay_02', 'WARN', 'Connection pool exhausted. Waiting for connection...', 'res_svc_payments', 'run_deploy_v45', datetime('now', '-4 hours', '-30 minutes'), '{}'),
('log_pay_03', 'ERROR', 'FATAL: Health check /livez failed. Database unavailable. Rolling back.', 'res_svc_payments', 'run_deploy_v45', datetime('now', '-4 hours', '-10 minutes'), '{}');

-- Incident
INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, closed_at, summary, attributes_json) VALUES
('inc_002', 'prod', 'Payment Gateway Deployment Failed', 'MEDIUM', 'RESOLVED', datetime('now', '-5 hours'), datetime('now', '-1 hour'), 'Deployment v45 failed due to DB connection saturation. Rolled back to v44.', '{"related_resource_id": "res_svc_payments"}');


-- ------------------------------------------------------------------------------------------------
-- SCENARIO 3: The "Silent Data Corruption" (Snowflake Table)
-- ------------------------------------------------------------------------------------------------

-- Resource: Customers Table
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, created_at, is_active) VALUES
('res_tbl_customers', 'snowflake_dw', 'prod', 'table', 'db.public.customers', 'customers_master', 'analytics', 'analytics_eng', '{"pii": "true"}', datetime('now', '-6 months'), 1);

-- Metric: Row count drops unexpectedly
INSERT INTO metric_point (metric_point_id, metric_name, metric_type, unit, value_number, resource_id, time, attributes_json) VALUES
('met_row_01', 'row_count', 'gauge', 'count', 10500, 'res_tbl_customers', datetime('now', '-2 days'), '{}'),
('met_row_02', 'row_count', 'gauge', 'count', 10550, 'res_tbl_customers', datetime('now', '-1 day'), '{}'),
('met_row_03', 'row_count', 'gauge', 'count', 0, 'res_tbl_customers', datetime('now', '-12 hours'), '{}'); -- DATA LOSS!

-- Incident
INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, closed_at, summary, attributes_json) VALUES
('inc_003', 'prod', 'Customer Master Table Empty', 'CRITICAL', 'OPEN', datetime('now', '-10 hours'), NULL, 'Automated checks detected 0 rows in the customer master table. Possible accidental truncate.', '{"related_resource_id": "res_tbl_customers"}');