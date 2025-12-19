-- sql/seed_reliability_data_demo.sql

-- 1. Platforms
INSERT INTO platform (platform_id, platform_type, display_name, attributes_json) VALUES
('aws_prod', 'cloud', 'AWS Production', '{"region": "us-east-1"}'),
('databricks_prod', 'data', 'Databricks Premium', '{"workspace": "12345"}'),
('snowflake_dw', 'warehouse', 'Snowflake DW', '{"account": "xy12345"}');

-- 2. Environments
INSERT INTO environment (env_id, env_type, region, attributes_json, name) VALUES
('prod', 'production', 'us-east-1', '{}', 'Production'),
('stage', 'staging', 'us-west-2', '{}', 'Staging');

-- 3. Resources
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, created_at, is_active) VALUES
('res_db_cust', 'snowflake_dw', 'prod', 'table', 'db.public.customers', 'customers_table', 'public', 'data_eng', '{}', datetime('now'), 1),
('res_job_etl', 'databricks_prod', 'prod', 'job', 'job-999', 'nightly_etl', 'jobs', 'data_eng', '{"priority": "high"}', datetime('now'), 1),
('res_s3_raw', 'aws_prod', 'prod', 'bucket', 'arn:aws:s3:::raw-data', 'raw-data-bucket', 'infra', 'devops', '{}', datetime('now'), 1);

-- 4. Runs (Recent history)
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, attempt, started_at, ended_at, message, attributes_json) VALUES
('run_101', 'databricks_prod', 'prod', 'res_job_etl', 'run-abc-1', 'batch', 'SUCCESS', 1, datetime('now', '-1 hour'), datetime('now', '-50 minutes'), 'Completed successfully', '{}'),
('run_102', 'databricks_prod', 'prod', 'res_job_etl', 'run-abc-2', 'batch', 'FAILED', 1, datetime('now', '-25 hours'), datetime('now', '-24 hours'), 'Timeout waiting for resources', '{}');

-- 5. Incidents
INSERT INTO incident (incident_id, env_id, title, severity, status, opened_at, closed_at, summary, attributes_json) VALUES
('inc_001', 'prod', 'ETL Job Failure', 'HIGH', 'RESOLVED', datetime('now', '-1 day'), datetime('now', '-20 hours'), 'The nightly ETL failed due to timeout.', '{}');

-- 6. Logs (Changed table name from log_event to log_record)
INSERT INTO log_record (log_id, severity_text, body, resource_id, run_id, time, attributes_json) VALUES
('log_001', 'ERROR', 'Connection timed out after 3000ms', 'res_job_etl', 'run_102', datetime('now', '-25 hours'), '{}');