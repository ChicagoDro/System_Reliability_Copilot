-- sql/seed_reliability_data_lite.sql
-- Phase 1 Seed Data: Multi-Platform Scenarios (Airflow, Databricks, dbt, K8s)

PRAGMA foreign_keys = ON;

-- 1. INFRASTRUCTURE
INSERT INTO platform (platform_id, platform_type, display_name) VALUES 
('airflow', 'orchestrator', 'Airflow Prod'),
('snowflake', 'warehouse', 'Snowflake Prod'),
('databricks', 'compute', 'Databricks Engineering'),
('dbt', 'transform', 'dbt Cloud'),
('k8s', 'compute', 'EKS Cluster US-East');

INSERT INTO environment (env_id, env_type, name) VALUES 
('prod', 'production', 'Production US');

-- ------------------------------------------------------------
-- SCENARIO A: AIRFLOW (Empty File -> DQ Failure)
-- ------------------------------------------------------------
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, name, namespace, owner)
VALUES ('res_ingest_vendor_daily', 'airflow', 'prod', 'dag', 'vendor_ingest_daily', 'ingestion_team', 'data_eng');

INSERT INTO dataset (dataset_id, platform_id, env_id, name, namespace, dataset_type)
VALUES ('ds_vendor_raw', 'snowflake', 'prod', 'VENDOR_RAW_TABLE', 'RAW_ZONE', 'table');

INSERT INTO dq_rule (rule_id, dataset_id, name, severity, rule_type, expression, description)
VALUES ('rule_chk_rows_nonzero', 'ds_vendor_raw', 'Row Count > 0', 'CRITICAL', 'row_count', 'count(*) > 0', 'Ensures vendor file was not empty');

INSERT INTO run (run_id, resource_id, platform_id, env_id, external_run_id, run_type, status, started_at, ended_at, message)
VALUES ('run_af_fail_001', 'res_ingest_vendor_daily', 'airflow', 'prod', 'dag_run_2025_12_18_001', 'scheduled', 'failed', datetime('now', '-2 hours'), datetime('now', '-1 hour'), 'Pipeline failed validation.');

INSERT INTO dq_result (dq_result_id, rule_id, run_id, dataset_id, status, observed_value, expected_value, event_ts, created_at)
VALUES ('dq_af_fail_001', 'rule_chk_rows_nonzero', 'run_af_fail_001', 'ds_vendor_raw', 'fail', '0', '> 0', datetime('now', '-1 hour', '-5 minutes'), datetime('now', '-1 hour', '-5 minutes'));

INSERT INTO log_record (log_id, run_id, severity_text, body, time) VALUES 
('log_af_01', 'run_af_fail_001', 'WARN', 'Detected empty input file.', datetime('now', '-1 hour', '-10 minutes')),
('log_af_02', 'run_af_fail_001', 'ERROR', 'DQ Validation Failed: Rule "Row Count > 0" returned 0.', datetime('now', '-1 hour', '-5 minutes'));

-- ------------------------------------------------------------
-- SCENARIO B: DATABRICKS (Schema Drift Incident)
-- ------------------------------------------------------------
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, name, namespace, owner)
VALUES ('res_dbx_silver_gold', 'databricks', 'prod', 'job', 'silver_to_gold_merge', 'core_banking', 'analytics_eng');

INSERT INTO dataset (dataset_id, platform_id, env_id, name, namespace, dataset_type)
VALUES ('ds_gold_transactions', 'databricks', 'prod', 'gold_transactions', 'finance', 'delta_table');

INSERT INTO dq_rule (rule_id, dataset_id, name, severity, rule_type, expression, description)
VALUES ('rule_schema_cols', 'ds_gold_transactions', 'Required Columns Present', 'CRITICAL', 'schema', 'columns_exist(["user_id", "amount"])', 'Checks for critical columns');

INSERT INTO run (run_id, resource_id, platform_id, env_id, external_run_id, run_type, status, started_at, ended_at, message)
VALUES ('run_dbx_fail_002', 'res_dbx_silver_gold', 'databricks', 'prod', 'job_run_99821', 'scheduled', 'failed', datetime('now', '-30 minutes'), datetime('now'), 'AnalysisException: cannot resolve column');

INSERT INTO log_record (log_id, run_id, severity_text, body, time) VALUES 
('log_dbx_01', 'run_dbx_fail_002', 'INFO', 'Starting Spark Session. Reading from Silver delta path.', datetime('now', '-29 minutes')),
('log_dbx_02', 'run_dbx_fail_002', 'ERROR', 'pyspark.sql.utils.AnalysisException: cannot resolve "user_id" given input columns: [transaction_id, amt, timestamp]', datetime('now', '-25 minutes')),
('log_dbx_03', 'run_dbx_fail_002', 'FATAL', 'Job aborted due to unrecoverable schema mismatch.', datetime('now', '-24 minutes'));

INSERT INTO dq_result (dq_result_id, rule_id, run_id, dataset_id, status, observed_value, expected_value, message, event_ts, created_at)
VALUES ('dq_dbx_fail_001', 'rule_schema_cols', 'run_dbx_fail_002', 'ds_gold_transactions', 'error', 'Missing: user_id', 'All columns present', 'Column user_id dropped in upstream', datetime('now', '-25 minutes'), datetime('now', '-25 minutes'));

-- ------------------------------------------------------------
-- SCENARIO C: DBT (Business Logic Failure)
-- ------------------------------------------------------------
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, name, namespace, owner)
VALUES ('res_dbt_monthly_kpis', 'dbt', 'prod', 'model', 'fct_monthly_kpis', 'finance', 'analytics_team');

INSERT INTO dataset (dataset_id, platform_id, env_id, name, namespace, dataset_type)
VALUES ('ds_fct_monthly_kpis', 'snowflake', 'prod', 'FCT_MONTHLY_KPIS', 'MART_FINANCE', 'view');

INSERT INTO dq_rule (rule_id, dataset_id, name, severity, rule_type, expression, description)
VALUES ('rule_dbt_unique_id', 'ds_fct_monthly_kpis', 'unique_id', 'WARN', 'uniqueness', 'count(id) == count(distinct id)', 'Primary key uniqueness');

INSERT INTO run (run_id, resource_id, platform_id, env_id, external_run_id, run_type, status, started_at, ended_at, message)
VALUES ('run_dbt_fail_003', 'res_dbt_monthly_kpis', 'dbt', 'prod', 'dbt_run_7721', 'manual', 'failed', datetime('now', '-4 hours'), datetime('now', '-3 hours'), 'dbt build failed');

INSERT INTO log_record (log_id, run_id, severity_text, body, time) VALUES 
('log_dbt_01', 'run_dbt_fail_003', 'INFO', 'Start model fct_monthly_kpis', datetime('now', '-4 hours')),
('log_dbt_02', 'run_dbt_fail_003', 'ERROR', 'Failure in test unique_fct_monthly_kpis_id. Got 5 failing rows.', datetime('now', '-3 hours', '-55 minutes'));

INSERT INTO dq_result (dq_result_id, rule_id, run_id, dataset_id, status, observed_value, expected_value, message, event_ts, created_at)
VALUES ('dq_dbt_fail_001', 'rule_dbt_unique_id', 'run_dbt_fail_003', 'ds_fct_monthly_kpis', 'fail', '5 duplicates', '0 duplicates', 'Duplicate IDs found in final aggregation', datetime('now', '-3 hours', '-55 minutes'), datetime('now', '-3 hours', '-55 minutes'));

-- ------------------------------------------------------------
-- SCENARIO D: REST API (Incident, No DQ)
-- ------------------------------------------------------------
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, name, namespace, owner)
VALUES ('res_svc_payment_api', 'k8s', 'prod', 'service', 'svc_payment_gateway', 'payments', 'backend_team');

INSERT INTO run (run_id, resource_id, platform_id, env_id, external_run_id, run_type, status, started_at, ended_at, message)
VALUES ('run_svc_deploy_v45', 'res_svc_payment_api', 'k8s', 'prod', 'deploy_v45_hash_abc', 'service_window', 'degraded', datetime('now', '-5 hours'), NULL, 'Active deployment currently experiencing issues');

INSERT INTO log_record (log_id, run_id, severity_text, body, time) VALUES 
('log_svc_01', 'run_svc_deploy_v45', 'INFO', 'Health check passed. Pod ready.', datetime('now', '-4 hours')),
('log_svc_02', 'run_svc_deploy_v45', 'WARN', 'Database connection pool usage at 85%.', datetime('now', '-30 minutes')),
('log_svc_03', 'run_svc_deploy_v45', 'ERROR', 'GET /api/v1/payments 500 Internal Server Error - Connection timed out to DB host.', datetime('now', '-25 minutes')),
('log_svc_04', 'run_svc_deploy_v45', 'FATAL', 'Circuit Breaker "PaymentDB" OPEN. Rejecting all traffic.', datetime('now', '-20 minutes'));