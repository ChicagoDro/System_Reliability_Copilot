-- sql/seed_reliability_data.sql
-- Reliability Copilot demo dataset
-- Supports: Failing Resources, SLA Breaches, Service Health

PRAGMA foreign_keys = ON;

-- ============================================================================
-- 0. PLATFORMS & ENVIRONMENTS
-- ============================================================================
INSERT INTO platform (platform_id, platform_type, display_name, attributes_json) VALUES
('aws_prod',        'cloud',        'AWS Production',       '{"region": "us-east-1"}'),
('databricks_prod', 'data',         'Databricks Premium',   '{"workspace": "db-12345", "cloud": "aws", "tier": "premium"}'),
('snowflake_dw',    'warehouse',    'Snowflake Analytics',  '{"account": "xy12345", "edition": "standard"}'),
('k8s_cluster',     'compute',      'EKS Cluster A',        '{"version": "1.29", "cni": "vpc-cni"}'),
('airflow_prod',    'orchestrator', 'Airflow Production',   '{"version": "2.8.1", "executor": "CeleryExecutor"}'),
('dbt_cloud',       'transform',    'dbt Cloud',            '{"account": "dbt-99"}');

INSERT INTO environment (env_id, env_type, region, attributes_json, name) VALUES
('prod',  'production', 'us-east-1', '{}', 'Production'),
('stage', 'staging',    'us-west-2', '{}', 'Staging');

-- ============================================================================
-- 1. COMPUTE CONFIGS
-- ============================================================================
INSERT INTO compute_config (compute_config_id, platform_id, env_id, config_type, config_json, config_hash) VALUES
('cfg_dbx_small',  'databricks_prod', 'prod', 'job_cluster',
 '{"driver_node_type_id": "i3.xlarge", "workers": 2, "spark_conf": {"spark.executor.memory": "4g", "spark.driver.memory": "4g"}}', 'hash_dbx_small'),
('cfg_dbx_medium', 'databricks_prod', 'prod', 'job_cluster',
 '{"driver_node_type_id": "i3.2xlarge", "workers": 4, "spark_conf": {"spark.executor.memory": "16g"}}', 'hash_dbx_med'),
('cfg_k8s_pay_api','k8s_cluster', 'prod', 'deployment_spec',
 '{"resources": {"limits": {"memory": "512Mi", "cpu": "500m"}}, "replicas": 3}', 'hash_k8s_pay'),
('cfg_k8s_nginx',  'k8s_cluster', 'prod', 'deployment_spec',
 '{"replicas": 2, "resources": {"limits": {"cpu": "200m"}}}', 'hash_k8s_nginx');

-- ============================================================================
-- 2. RESOURCES
-- ============================================================================
INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, is_active) VALUES
('res_job_nightly_fact', 'databricks_prod', 'prod', 'job',      'job-555',             'nightly_fact_aggregation',  'finance_data',  'data_eng',       '{"priority": "critical", "sla_runtime_mins": 60}', 1),
('res_job_silver_gold',  'databricks_prod', 'prod', 'job',      'job-777',             'silver_to_gold_merge',      'core_banking',  'analytics_eng',  '{"priority": "high"}',                             1),
('res_job_reg_report',   'databricks_prod', 'prod', 'job',      'job-reg-001',         'monthly_regulatory_report', 'compliance',    'compliance_team','{"sla_runtime_mins": 30, "priority": "p0"}',        1),
('res_tbl_customers',    'snowflake_dw',    'prod', 'table',    'db.public.customers', 'customers_master',          'analytics',     'analytics_eng',  '{"retention_days": 1}',                            1),
('res_af_vendor_dag',    'airflow_prod',    'prod', 'dag',      'dag_vendor_ingest',   'vendor_ingest_daily',       'ingestion',     'data_eng',       '{}',                                               1),
('res_dbt_kpis',         'dbt_cloud',       'prod', 'model',    'model.fct_monthly_kpis','fct_monthly_kpis',        'finance',       'analytics_team', '{}',                                               1),
('res_svc_payments',     'k8s_cluster',     'prod', 'service',  'svc-pay-99',          'payment_gateway_api',       'payments',      'backend_team',   '{}',                                               1),
('res_api_backend',      'k8s_cluster',     'prod', 'service',  'svc-api-01',          'checkout-api',              'backend',       'backend_team',   '{}',                                               1),
('res_web_nginx',        'k8s_cluster',     'prod', 'service',  'svc-nginx-01',        'frontend-nginx',            'web',           'frontend_team',  '{}',                                               1),
('res_db_postgres',      'aws_prod',        'prod', 'database', 'db-rds-009',          'users_db_primary',          'rds',           'dba_team',       '{}',                                               1);

INSERT INTO resource (resource_id, platform_id, env_id, resource_type, external_id, name, namespace, owner, attributes_json, is_active) VALUES
('res_tbl_raw_events',     'snowflake_dw', 'prod', 'table',           'db.raw.events',           'raw_events',            'raw',     'data_eng', '{"retention_days": 7}',   1),
('res_tbl_fact_daily',     'snowflake_dw', 'prod', 'table',           'db.analytics.fact_daily', 'fact_aggregates_daily', 'analytics','data_eng','{"retention_days": 365}', 1),
('res_tbl_vendor_staging', 'snowflake_dw', 'prod', 'table',           'db.staging.vendor_feed',  'vendor_staging',        'staging', 'data_eng', '{}',                      1),
('res_ext_vendor_sftp',    'aws_prod',     'prod', 'external_system', 'sftp://vendor.com',        'Vendor SFTP Server',   'external','vendor',   '{}',                      1);

-- ============================================================================
-- 3. LINEAGE
-- ============================================================================
INSERT INTO lineage_edge (edge_id, env_id, src_resource_id, dst_resource_id, relation_type) VALUES
('edge_1',          'prod', 'res_af_vendor_dag',    'res_dbt_kpis',          'TRIGGERS'),
('edge_2',          'prod', 'res_dbt_kpis',         'res_job_reg_report',    'FEEDS'),
('edge_3',          'prod', 'res_svc_payments',     'res_db_postgres',       'CONNECTS_TO'),
('edge_4',          'prod', 'res_api_backend',      'res_svc_payments',      'CALLS'),
('edge_5',          'prod', 'res_web_nginx',        'res_api_backend',       'CALLS'),
('edge_fact_in_1',  'prod', 'res_tbl_raw_events',   'res_job_nightly_fact',  'FEEDS'),
('edge_fact_in_2',  'prod', 'res_tbl_customers',    'res_job_nightly_fact',  'FEEDS'),
('edge_fact_out_1', 'prod', 'res_job_nightly_fact', 'res_tbl_fact_daily',    'PRODUCES'),
('edge_fact_out_2', 'prod', 'res_tbl_fact_daily',   'res_dbt_kpis',          'FEEDS'),
('edge_reg_in_1',   'prod', 'res_tbl_fact_daily',   'res_job_reg_report',    'FEEDS'),
('edge_pipe_1',     'prod', 'res_ext_vendor_sftp',  'res_af_vendor_dag',     'FEEDS'),
('edge_pipe_2',     'prod', 'res_af_vendor_dag',    'res_tbl_vendor_staging','PRODUCES'),
('edge_pipe_3',     'prod', 'res_tbl_vendor_staging','res_dbt_kpis',         'FEEDS'),
('edge_web_1',      'prod', 'res_web_nginx',        'res_api_backend',       'CALLS'),
('edge_api_1',      'prod', 'res_api_backend',      'res_svc_payments',      'CALLS'),
('edge_pay_1',      'prod', 'res_svc_payments',     'res_db_postgres',       'WRITES_TO'),
('edge_api_2',      'prod', 'res_api_backend',      'res_db_postgres',       'READS_FROM');

-- ============================================================================
-- 4. SCENARIOS
-- ============================================================================

-- --- SCENARIO 1: Databricks OOM ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, compute_config_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_fact_100', 'databricks_prod', 'prod', 'res_job_nightly_fact', 'cfg_dbx_small', 'run-abc-99',  'batch', 'SUCCESS', datetime('now', '-26 hours'), datetime('now', '-25 hours'), 'Succeeded'),
('run_fact_101', 'databricks_prod', 'prod', 'res_job_nightly_fact', 'cfg_dbx_small', 'run-abc-101', 'batch', 'FAILED',  datetime('now', '-3 hours'),  datetime('now', '-2 hours'),  'Job failed with exit code 137 (OOMKilled): java.lang.OutOfMemoryError: Java heap space');

INSERT INTO metric_point (metric_point_id, resource_id, run_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_jvm_01', 'res_job_nightly_fact', 'run_fact_101', 'jvm_heap_usage', 'gauge', 'mb', 3800, datetime('now', '-2 hours', '-30 minutes')),
('met_jvm_02', 'res_job_nightly_fact', 'run_fact_101', 'jvm_heap_usage', 'gauge', 'mb', 4150, datetime('now', '-2 hours', '-15 minutes'));

-- --- SCENARIO 2: K8s Service Crash ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, compute_config_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_deploy_v45', 'k8s_cluster', 'prod', 'res_svc_payments', 'cfg_k8s_pay_api', 'deploy-v45', 'deploy', 'FAILED', datetime('now', '-5 hours'), datetime('now', '-4 hours'), 'OOMKilled: container exceeded memory limit 512Mi');

INSERT INTO metric_point (metric_point_id, resource_id, run_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_k8s_mem_01', 'res_svc_payments', 'run_deploy_v45', 'container_memory_usage_bytes', 'gauge', 'mb', 540, datetime('now', '-4 hours', '-5 minutes'));

-- --- SCENARIO 3: Snowflake Data Loss ---
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_row_01', 'res_tbl_customers', 'row_count', 'gauge', 'count', 10500, datetime('now', '-3 days')),
('met_row_04', 'res_tbl_customers', 'row_count', 'gauge', 'count', 0,     datetime('now', '-1 hour'));

-- --- SCENARIO 4: Airflow Failure ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_af_daily_001', 'airflow_prod', 'prod', 'res_af_vendor_dag', 'run_2025_12_18', 'scheduled', 'FAILED', datetime('now', '-8 hours'), datetime('now', '-7 hours'), 'Upstream validation failed: vendor file row_count = 0');

-- --- SCENARIO 5: Schema Drift ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_dbx_drift_001', 'databricks_prod', 'prod', 'res_job_silver_gold', 'run-drift-99', 'batch', 'FAILED', datetime('now', '-30 minutes'), datetime('now'), 'AnalysisException: cannot resolve column "user_id" given input columns');

-- --- SCENARIO 6: dbt Run Failure ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, external_run_id, run_type, status, started_at, ended_at, message) VALUES
('run_dbt_fail_99', 'dbt_cloud', 'prod', 'res_dbt_kpis', 'dbt-run-4421', 'build', 'FAILED', datetime('now', '-1 day'), datetime('now', '-23 hours'), 'Tests failed: unique_fct_monthly_kpis_id — 5 failing rows');

INSERT INTO metric_point (metric_point_id, resource_id, run_id, metric_name, metric_type, unit, value_number, time) VALUES
('met_dbt_in',  'res_dbt_kpis', 'run_dbt_fail_99', 'row_count_input',  'gauge', 'count', 50000, datetime('now', '-23 hours', '-10 minutes')),
('met_dbt_out', 'res_dbt_kpis', 'run_dbt_fail_99', 'row_count_output', 'gauge', 'count', 50005, datetime('now', '-23 hours', '-5 minutes'));

-- --- SCENARIO 7: SLA Breach (Regulatory Report) ---
WITH RECURSIVE runs(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM runs WHERE x<20)
INSERT INTO run (run_id, platform_id, env_id, resource_id, compute_config_id, run_type, status, started_at, ended_at, message)
SELECT
    'run_reg_' || x, 'databricks_prod', 'prod', 'res_job_reg_report', 'cfg_dbx_medium', 'batch', 'SUCCESS',
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

-- --- SCENARIO 8: Service Health / Latency Spike ---
INSERT INTO run (run_id, platform_id, env_id, resource_id, compute_config_id, run_type, status, started_at, ended_at, message) VALUES
('deploy_api_v40', 'k8s_cluster', 'prod', 'res_api_backend', 'cfg_k8s_nginx', 'deploy', 'SUCCESS', datetime('now', '-24 hours'), datetime('now', '-23 hours', '-50 minutes'), 'Active');

WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_lat_api_' || x, 'res_api_backend', 'latency_p95', 'gauge', 'ms',
    CASE WHEN x < 4 THEN 2500 ELSE 45 END, datetime('now', '-' || x || ' hours') FROM hours;

WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_cpu_api_' || x, 'res_api_backend', 'container_cpu_usage_seconds_total', 'gauge', 'cores',
    CASE WHEN x < 4 THEN 0.2 ELSE 0.02 END, datetime('now', '-' || x || ' hours') FROM hours;

WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_rps_api_' || x, 'res_api_backend', 'http_requests_per_second', 'gauge', 'rps',
    CASE WHEN x < 4 THEN 2000 ELSE 100 END, datetime('now', '-' || x || ' hours') FROM hours;

WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_err_api_' || x, 'res_api_backend', 'http_error_rate_5xx', 'gauge', 'count',
    CASE WHEN x < 4 THEN 50 ELSE 0 END, datetime('now', '-' || x || ' hours') FROM hours;

WITH RECURSIVE hours(x) AS (SELECT 0 UNION ALL SELECT x+1 FROM hours WHERE x<24)
INSERT INTO metric_point (metric_point_id, resource_id, metric_name, metric_type, unit, value_number, time)
SELECT 'met_replicas_api_' || x, 'res_api_backend', 'pod_replica_count', 'gauge', 'count',
    2, datetime('now', '-' || x || ' hours') FROM hours;

-- ============================================================================
-- 5. SLA POLICIES
-- ============================================================================
INSERT INTO sla_policy (sla_id, resource_id, max_duration_seconds, availability_target, attributes_json) VALUES
('sla_001', 'res_job_nightly_fact', 3600, 0.995,  '{"business_impact": "P0 - blocks regulatory reporting", "oncall_team": "data-engineering", "sla_window": "00:00-06:00 UTC"}'),
('sla_002', 'res_job_reg_report',   1800, 0.99,   '{"business_impact": "P0 - SEC filing deadline 8AM EST", "oncall_team": "compliance-team", "escalation_after_minutes": 15}'),
('sla_003', 'res_svc_payments',     NULL, 0.9999, '{"business_impact": "P0 - payment processing", "max_latency_p95_ms": 200, "oncall_team": "backend-team"}'),
('sla_004', 'res_api_backend',      NULL, 0.999,  '{"business_impact": "P1 - customer checkout", "max_latency_p95_ms": 500, "oncall_team": "backend-team"}'),
('sla_005', 'res_tbl_customers',    NULL, NULL,   '{"business_impact": "P0 - master data", "max_staleness_hours": 1, "min_row_count": 10000}'),
('sla_006', 'res_tbl_fact_daily',   NULL, NULL,   '{"business_impact": "P1 - analytics dependency", "max_staleness_hours": 4, "min_row_count": 1000}');

-- ============================================================================
-- 6. RESOURCE OWNERSHIP
-- ============================================================================
CREATE TABLE IF NOT EXISTS resource_owner (
    owner_id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    team_name TEXT NOT NULL,
    oncall_rotation TEXT,
    slack_channel TEXT,
    pagerduty_service_id TEXT,
    email TEXT,
    escalation_policy TEXT,
    FOREIGN KEY(resource_id) REFERENCES resource(resource_id)
);

INSERT INTO resource_owner (owner_id, resource_id, team_name, oncall_rotation, slack_channel, pagerduty_service_id, email, escalation_policy) VALUES
('own_001', 'res_job_nightly_fact', 'data-engineering', 'weekly', '#data-eng-oncall',    'PDATA001', 'data-eng@company.com',   'escalate_to_vp_after_1hr'),
('own_002', 'res_job_reg_report',   'compliance-team',  'daily',  '#compliance-critical','PCOMP002', 'compliance@company.com', 'escalate_to_cfo_immediately'),
('own_003', 'res_svc_payments',     'backend-team',     'daily',  '#backend-oncall',     'PBACK003', 'backend@company.com',    'escalate_to_cto_after_15min'),
('own_004', 'res_api_backend',      'backend-team',     'daily',  '#backend-oncall',     'PBACK003', 'backend@company.com',    'standard'),
('own_005', 'res_tbl_customers',    'dba-team',         'weekly', '#dba-alerts',         'PDBA005',  'dba@company.com',        'standard'),
('own_006', 'res_af_vendor_dag',    'data-engineering', 'weekly', '#data-eng-oncall',    'PDATA001', 'data-eng@company.com',   'standard'),
('own_007', 'res_dbt_kpis',         'analytics-team',   'none',   '#analytics-team',     NULL,       'analytics@company.com',  'email_only');

-- ============================================================================
-- 7. CHANGE HISTORY
-- ============================================================================
CREATE TABLE IF NOT EXISTS resource_change (
    change_id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    changed_by TEXT,
    change_summary TEXT,
    diff_json TEXT,
    jira_ticket TEXT,
    changed_at TEXT NOT NULL,
    FOREIGN KEY(resource_id) REFERENCES resource(resource_id)
);

INSERT INTO resource_change (change_id, resource_id, change_type, changed_by, change_summary, diff_json, jira_ticket, changed_at) VALUES
('chg_001', 'res_job_nightly_fact', 'CONFIG_CHANGE', 'platform-eng-bot',
 'Cost optimization: Reduced cluster size from medium to small',
 '{"before": {"cluster": "cfg_dbx_medium", "workers": 4, "driver_memory": "16g"}, "after": {"cluster": "cfg_dbx_small", "workers": 2, "driver_memory": "4g"}}',
 'OPS-1234', datetime('now', '-5 days')),

('chg_002', 'res_api_backend', 'DEPLOYMENT', 'ci-cd-pipeline',
 'Deployed v2.40: New Redis caching layer',
 '{"version": "v2.40", "commit": "abc123", "replicas": 2, "image": "api:v2.40"}',
 'BE-5678', datetime('now', '-24 hours')),

('chg_003', 'res_job_silver_gold', 'SCHEMA_CHANGE', 'analytics-team',
 'Added user_id column to silver.customers table',
 '{"table": "silver.customers", "added_columns": ["user_id"], "downstream_jobs_affected": ["res_job_silver_gold"]}',
 'DATA-9999', datetime('now', '-1 hour')),

('chg_004', 'res_tbl_customers', 'SCHEMA_CHANGE', 'john.doe@company.com',
 'DROP TABLE customers_master (ACCIDENTAL)',
 '{"action": "DROP", "rows_lost": 10500, "recovery_attempted": "UNDROP", "recovery_failed_reason": "retention_period_expired"}',
 NULL, datetime('now', '-2 days'));

-- ============================================================================
-- 8. RUN DEPENDENCIES
-- ============================================================================
CREATE TABLE IF NOT EXISTS run_dependency (
    upstream_run_id TEXT NOT NULL,
    downstream_run_id TEXT NOT NULL,
    dependency_type TEXT,
    PRIMARY KEY (upstream_run_id, downstream_run_id),
    FOREIGN KEY(upstream_run_id) REFERENCES run(run_id),
    FOREIGN KEY(downstream_run_id) REFERENCES run(run_id)
);

INSERT INTO run_dependency (upstream_run_id, downstream_run_id, dependency_type) VALUES
('run_af_daily_001', 'run_dbt_fail_99', 'TRIGGERS'),
('run_dbt_fail_99',  'run_reg_15',      'BLOCKS'),
('run_dbt_fail_99',  'run_reg_16',      'BLOCKS'),
('run_dbt_fail_99',  'run_reg_17',      'BLOCKS');

UPDATE run SET parent_run_id = 'run_af_daily_001' WHERE run_id = 'run_dbt_fail_99';
UPDATE run SET parent_run_id = 'run_dbt_fail_99'  WHERE run_id LIKE 'run_reg_%' AND run_id >= 'run_reg_15';

-- ============================================================================
-- 9. BASELINES
-- ============================================================================
CREATE TABLE IF NOT EXISTS resource_baseline (
    baseline_id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    baseline_type TEXT NOT NULL,
    value_number REAL NOT NULL,
    unit TEXT,
    lookback_days INTEGER DEFAULT 30,
    calculated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(resource_id) REFERENCES resource(resource_id)
);

INSERT INTO resource_baseline (baseline_id, resource_id, metric_name, baseline_type, value_number, unit, lookback_days) VALUES
('base_001', 'res_job_nightly_fact', 'duration_minutes', 'p50',     55,     'minutes', 30),
('base_002', 'res_job_nightly_fact', 'duration_minutes', 'p95',     65,     'minutes', 30),
('base_003', 'res_job_reg_report',   'duration_minutes', 'p50',     25,     'minutes', 30),
('base_004', 'res_job_reg_report',   'duration_minutes', 'p95',     30,     'minutes', 30),
('base_005', 'res_api_backend',      'latency_p95_ms',   'average', 45,     'ms',      7),
('base_006', 'res_svc_payments',     'latency_p95_ms',   'average', 25,     'ms',      7),
('base_007', 'res_tbl_customers',    'row_count',        'average', 10500,  'count',   30),
('base_008', 'res_tbl_fact_daily',   'row_count',        'average', 250000, 'count',   30);
