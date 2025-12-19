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
VENDOR_DOCS_INDEX_PATH = INDEX_DIR / "databricks_docs"

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
        "https://docs.databricks.com/en/jobs/settings.html",  # Retries/Timeouts
        "https://docs.databricks.com/en/delta/history.html",  # Delta History
    ],
    "snowflake": [
        "https://docs.snowflake.com/en/user-guide/data-time-travel", # For "Undrop" scenario
        "https://docs.snowflake.com/en/user-guide/data-time-travel-undrop",
    ],
    "k8s": [
        "https://kubernetes.io/docs/concepts/services-networking/service/", # For Service/Connection failures
        "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
    ],
    "airflow": [
        "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html", # For Empty File Sensor
        "https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html",
    ],
    "dbt": [
        "https://docs.getdbt.com/docs/build/tests", # For Unique/Not Null tests
        "https://docs.getdbt.com/docs/build/materializations",
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
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")

DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

def get_chat_model_name() -> str:
    if LLM_PROVIDER == "openai": return OPENAI_CHAT_MODEL
    if LLM_PROVIDER == "gemini": return GEMINI_CHAT_MODEL
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

def get_embed_model_name() -> str:
    if LLM_PROVIDER == "openai": return OPENAI_EMBED_MODEL
    if LLM_PROVIDER == "gemini": return GEMINI_EMBED_MODEL
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")