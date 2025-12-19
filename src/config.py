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

# Index directory (default: ./indexes)
INDEX_DIR = Path(os.getenv("INDEX_DIR", str(PROJECT_ROOT / "indexes")))

RELIABILITY_EVIDENCE_INDEX_LITE = INDEX_DIR / "reliability_evidence_lite"
RELIABILITY_EVIDENCE_INDEX_DEMO = INDEX_DIR / "reliability_evidence_demo"
RELIABILITY_RUNBOOKS_INDEX_LITE = INDEX_DIR / "reliability_runbooks_lite"
RELIABILITY_RUNBOOKS_INDEX_DEMO = INDEX_DIR / "reliability_runbooks_demo"

# MATCHING YOUR CODE: You renamed this to VENDOR_DOCS_INDEX_PATH
VENDOR_DOCS_INDEX_PATH = INDEX_DIR / "vendor_docs_databricks"

# --------------------------------------------------------------------------------------
# Databricks documentation corpus (vendor knowledge)
# --------------------------------------------------------------------------------------

DOCS_SITEMAP_URL = os.getenv("DOCS_SITEMAP_URL", "https://docs.databricks.com/aws/en/sitemap.xml")
DOCS_URL_PREFIX = os.getenv("DOCS_URL_PREFIX", "https://docs.databricks.com/aws/en/compute/")

# --------------------------------------------------------------------------------------
# Retrieval / chunking config
# --------------------------------------------------------------------------------------

# Chunking for PDFs / long text
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# Top-k for retriever
RUNBOOKS_RETRIEVER_K = int(os.getenv("RUNBOOKS_RETRIEVER_K", "4"))
DOCS_RETRIEVER_K = int(os.getenv("DOCS_RETRIEVER_K", "4"))

# --------------------------------------------------------------------------------------
# LLM / embeddings
# --------------------------------------------------------------------------------------

LLM_PROVIDER = os.getenv("LLM_PROVIDER", os.getenv("EMBEDDINGS_PROVIDER", "openai")).lower()

OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

# CRITICAL FIX: Must be 'text-embedding-3-large' to match ingest_runbooks.py (3072 dims).
# This fixes the AssertionError.
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")

GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-1.5-pro")
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/text-embedding-004")

GROK_CHAT_MODEL = os.getenv("GROK_CHAT_MODEL", "grok-beta")
GROK_EMBED_MODEL = os.getenv("GROK_EMBED_MODEL", "grok-embed") 

DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "4"))

def get_chat_model_name() -> str:
    if LLM_PROVIDER == "openai":
        return OPENAI_CHAT_MODEL
    if LLM_PROVIDER == "gemini":
        return GEMINI_CHAT_MODEL
    if LLM_PROVIDER == "grok":
        return GROK_CHAT_MODEL
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

def get_embed_model_name() -> str:
    if LLM_PROVIDER == "openai":
        return OPENAI_EMBED_MODEL
    if LLM_PROVIDER == "gemini":
        return GEMINI_EMBED_MODEL
    if LLM_PROVIDER == "grok":
        return GROK_EMBED_MODEL
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")