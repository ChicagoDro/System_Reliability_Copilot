# src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Reliability Copilot DB (SQLite)
RELIABILITY_DB_PATH = PROJECT_ROOT / "data" / "reliability.db"

# Index directory
INDEX_DIR = Path(os.getenv("INDEX_DIR", str(PROJECT_ROOT / "indexes")))

# Unified Index Paths
RELIABILITY_EVIDENCE_INDEX_PATH = INDEX_DIR / "reliability_evidence"
RELIABILITY_RUNBOOKS_INDEX_PATH = INDEX_DIR / "reliability_runbooks"
VENDOR_DOCS_INDEX_PATH = INDEX_DIR / "vendor_docs"

# --------------------------------------------------------------------------------------
# Databricks documentation corpus
# --------------------------------------------------------------------------------------
DOCS_SITEMAP_URL = os.getenv("DOCS_SITEMAP_URL", "https://docs.databricks.com/aws/en/sitemap.xml")
DOCS_URL_PREFIX = os.getenv("DOCS_URL_PREFIX", "https://docs.databricks.com/aws/en/compute/")

# --------------------------------------------------------------------------------------
# Vendor Documentation URLs (The "Sniper List")
# --------------------------------------------------------------------------------------
VENDOR_DOCS_URLS = {
    "databricks": [
        "https://docs.databricks.com/en/compute/pool-best-practices.html",
        "https://docs.databricks.com/en/jobs/settings.html",
        "https://docs.databricks.com/aws/en/compute/configure",
        "https://docs.databricks.com/en/delta/history.html",
        # NEW: The "Answer Key" for your Schema Drift Scenario
        "https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema", 
        "https://docs.databricks.com/aws/en/data-engineering/schema-evolution",
    ],
    "snowflake": [
        "https://docs.snowflake.com/en/user-guide/tables-iceberg-best-practices",
        "https://docs.snowflake.com/en/user-guide/data-time-travel",
        "https://docs.snowflake.com/en/user-guide/data-time-travel-undrop",
        # NEW: Critical for understanding Cost/Credit Limits
        "https://docs.snowflake.com/en/user-guide/resource-monitors.html",
        "https://docs.snowflake.com/en/sql-reference/sql/undrop-table.html",
    ],
    "k8s": [
        "https://kubernetes.io/docs/concepts/services-networking/service/",
        "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
        "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/",
        "https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/",
        # NEW: The "Physics" of your OOM and Traffic Spike scenarios
        "https://kubernetes.io/docs/concepts/policy/resource-quotas/", 
        "https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/",
    ],
    "sre_principles": [
        "https://sre.google/sre-book/service-level-objectives/",
        "https://sre.google/sre-book/monitoring-distributed-systems/",
        "https://sre.google/sre-book/golden-signals/"
    ],
    "airflow": [
        "https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html",
        "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html",
        "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html",
        # NEW: Explains the difference between SLA (Notification) and Timeout (Failure)
        "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/tasks.html",
    ],
    "ec2": [
        "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-best-practices.html",
        "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html",
        "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring_ec2.html",
        # NEW: Critical for Cost Optimization scenarios
        "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html",
    ],
    "dbt": [
        "https://docs.getdbt.com/best-practices",
        "https://docs.getdbt.com/docs/build/data-tests",
        "https://docs.getdbt.com/docs/build/incremental-models",
        "https://docs.getdbt.com/guides/debug-errors",
        # NEW: The direct fix for your "KPI Duplicates" scenario
        "https://docs.getdbt.com/reference/resource-configs/unique_key",
        "https://docs.getdbt.com/docs/build/incremental-strategy",
    ]
}

# --------------------------------------------------------------------------------------
# Retrieval / chunking config
# --------------------------------------------------------------------------------------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
RUNBOOKS_RETRIEVER_K = int(os.getenv("RUNBOOKS_RETRIEVER_K", "4"))
DOCS_RETRIEVER_K = int(os.getenv("DOCS_RETRIEVER_K", "4"))

# --------------------------------------------------------------------------------------
# LLM / embeddings
# --------------------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", os.getenv("EMBEDDINGS_PROVIDER", "openai")).lower()

OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")

GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-pro")
# Support both GEMINI_EMBED_MODEL and GEMINI_EMBEDDING_MODEL (legacy key)
# Default to gemini-embedding-001 which is supported by the v1beta API used by langchain-google-genai 4.x
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL") or os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

def get_chat_model_name() -> str:
    if LLM_PROVIDER == "openai": return OPENAI_CHAT_MODEL
    if LLM_PROVIDER == "gemini": return GEMINI_CHAT_MODEL
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

def get_embed_model_name() -> str:
    if LLM_PROVIDER == "openai": return OPENAI_EMBED_MODEL
    if LLM_PROVIDER == "gemini": return GEMINI_EMBED_MODEL
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

# --------------------------------------------------------------------------------------
# Neo4j
# --------------------------------------------------------------------------------------
NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Vector index names (created during ingestion, referenced during retrieval)
NEO4J_VENDOR_DOCS_INDEX = os.getenv("NEO4J_VENDOR_DOCS_INDEX", "vendor_docs")
NEO4J_RUNBOOKS_INDEX    = os.getenv("NEO4J_RUNBOOKS_INDEX",    "runbooks")