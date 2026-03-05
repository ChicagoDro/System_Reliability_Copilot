-- sql/created_tables.sql
-- Reliability Copilot (SQLite) Schema
-- Supports: Failing Resources, SLA Breaches, Service Health

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
-- Metrics
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS metric_point (
  metric_point_id TEXT PRIMARY KEY,
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

-- ------------------------------------------------------------
-- Lineage
-- ------------------------------------------------------------

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
-- SLA
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sla_policy (
  sla_id TEXT PRIMARY KEY,
  resource_id TEXT NOT NULL,
  max_duration_seconds INTEGER,
  availability_target REAL,
  attributes_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
