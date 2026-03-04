-- sql/created_tables.sql
-- Reliability Copilot (SQLite) Phase 1 Schema
-- Fixes: Unified log_record, enhanced cost_record, added dq_result.created_at

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Core dimensions
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS platform (
  platform_id TEXT PRIMARY KEY,
  platform_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  attributes_json TEXT
);

CREATE TABLE IF NOT EXISTS environment (
  env_id TEXT PRIMARY KEY,
  env_type TEXT NOT NULL,
  name TEXT,
  region TEXT,
  attributes_json TEXT
);

CREATE TABLE IF NOT EXISTS resource (
  resource_id TEXT PRIMARY KEY,
  platform_id TEXT NOT NULL,
  env_id TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  external_id TEXT,
  name TEXT NOT NULL,
  namespace TEXT,
  owner TEXT,
  attributes_json TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  is_active INTEGER NOT NULL DEFAULT 1,
  
  FOREIGN KEY(platform_id) REFERENCES platform(platform_id),
  FOREIGN KEY(env_id) REFERENCES environment(env_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_resource_nk
  ON resource(platform_id, env_id, resource_type, COALESCE(external_id,''));

-- ------------------------------------------------------------
-- Executions & Config
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS compute_config (
  compute_config_id TEXT PRIMARY KEY,
  platform_id TEXT NOT NULL,
  env_id TEXT NOT NULL,
  config_type TEXT NOT NULL,
  config_json TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),

  FOREIGN KEY(platform_id) REFERENCES platform(platform_id),
  FOREIGN KEY(env_id) REFERENCES environment(env_id)
);

CREATE TABLE IF NOT EXISTS run (
  run_id TEXT PRIMARY KEY,
  platform_id TEXT NOT NULL,
  env_id TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  compute_config_id TEXT,
  external_run_id TEXT,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  attempt INTEGER DEFAULT 1,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  message TEXT,
  attributes_json TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  parent_run_id TEXT,
  trigger_user TEXT,
  
  FOREIGN KEY(resource_id) REFERENCES resource(resource_id),
  FOREIGN KEY(compute_config_id) REFERENCES compute_config(compute_config_id)
);

CREATE INDEX IF NOT EXISTS ix_run_resource_time ON run(resource_id, started_at);

-- ------------------------------------------------------------
-- Data Quality & Assets
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dataset (
    dataset_id TEXT PRIMARY KEY,
    platform_id TEXT NOT NULL,
    env_id TEXT NOT NULL,
    name TEXT NOT NULL,
    namespace TEXT,
    owner TEXT,
    dataset_type TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    attributes_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS dq_rule (
    rule_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    severity TEXT,
    rule_type TEXT, -- e.g. 'row_count', 'freshness'
    expression TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS dq_result (
    dq_result_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    run_id TEXT,
    dataset_id TEXT,
    status TEXT NOT NULL, -- PASS | WARN | FAIL | ERROR
    observed_value TEXT,
    expected_value TEXT,
    message TEXT,
    failed_rows INTEGER,
    event_ts TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')), -- Added for dq.py sort
    
    FOREIGN KEY(rule_id) REFERENCES dq_rule(rule_id),
    FOREIGN KEY(run_id) REFERENCES run(run_id)
);

-- ------------------------------------------------------------
-- Observability (Logs, Metrics, Traces)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS otel_resource (
  otel_resource_id TEXT PRIMARY KEY,
  schema_url TEXT,
  attributes_json TEXT
);

CREATE TABLE IF NOT EXISTS otel_scope (
  otel_scope_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT,
  schema_url TEXT
);

-- UNIFIED Log Table (Matches incidents.py and observability.py)
CREATE TABLE IF NOT EXISTS log_record (
    log_id TEXT PRIMARY KEY,
    otel_resource_id TEXT,
    otel_scope_id TEXT,
    resource_id TEXT,
    run_id TEXT,
    severity_text TEXT,   -- 'INFO', 'WARN', 'ERROR'
    severity_number INTEGER,
    body TEXT NOT NULL,
    attributes_json TEXT,
    trace_id TEXT,
    otel_span_id TEXT,
    time TEXT NOT NULL,
    
    FOREIGN KEY(resource_id) REFERENCES resource(resource_id),
    FOREIGN KEY(run_id) REFERENCES run(run_id)
);
CREATE INDEX IF NOT EXISTS ix_log_time ON log_record(time);

CREATE TABLE IF NOT EXISTS metric_point (
  metric_point_id TEXT PRIMARY KEY,
  otel_resource_id TEXT,
  otel_scope_id TEXT,
  resource_id TEXT,
  run_id TEXT,
  metric_name TEXT NOT NULL,
  metric_type TEXT NOT NULL,
  unit TEXT,
  value_number REAL,
  value_json TEXT,
  attributes_json TEXT,
  start_time TEXT,
  time TEXT NOT NULL,
  
  FOREIGN KEY(run_id) REFERENCES run(run_id)
);

CREATE TABLE IF NOT EXISTS trace_span (
  span_id TEXT PRIMARY KEY,
  trace_id TEXT NOT NULL,
  parent_span_id TEXT,
  otel_resource_id TEXT,
  otel_scope_id TEXT,
  resource_id TEXT,
  run_id TEXT,
  span_name TEXT NOT NULL,
  span_kind TEXT,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  status_code TEXT,
  status_message TEXT,
  attributes_json TEXT
);

-- ------------------------------------------------------------
-- Cost & Lineage
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cost_record (
    cost_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    env_id TEXT NOT NULL,
    compute_type TEXT,
    dbu REAL,
    cost_usd REAL,
    currency TEXT DEFAULT 'USD', -- Added for cost.py
    attributes_json TEXT,        -- Added for cost.py
    start_ts TEXT,
    end_ts TEXT,
    time TEXT,                   -- Added for sort order
    
    FOREIGN KEY(run_id) REFERENCES run(run_id)
);

CREATE TABLE IF NOT EXISTS lineage_edge (
  edge_id TEXT PRIMARY KEY,
  env_id TEXT NOT NULL,
  run_id TEXT,
  src_resource_id TEXT NOT NULL,
  dst_resource_id TEXT NOT NULL,
  confidence REAL DEFAULT 1.0,
  relation_type TEXT NOT NULL,
  attributes_json TEXT,
  created_at TEXT DEFAULT (datetime('now')),

  FOREIGN KEY(src_resource_id) REFERENCES resource(resource_id),
  FOREIGN KEY(dst_resource_id) REFERENCES resource(resource_id)
);

-- ------------------------------------------------------------
-- Incidents & SLA
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS incident (
  incident_id TEXT PRIMARY KEY,
  env_id TEXT NOT NULL,
  title TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  summary TEXT,
  attributes_json TEXT
);

CREATE TABLE IF NOT EXISTS incident_resource (
  incident_id TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  relation TEXT NOT NULL,
  PRIMARY KEY (incident_id, resource_id)
);

CREATE TABLE IF NOT EXISTS sla_policy (
  sla_id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL,
  max_duration_seconds INTEGER,
  max_cost_usd REAL,
  availability_target REAL,
  attributes_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);