# Makefile — System Reliability Copilot
# Neo4j-backed pipeline.

PYTHON       := .venv/bin/python
DB_PATH      := data/reliability.db
SQL_DIR      := src/setup
RUNBOOKS_DIR := src/runbooks

# ------------------------------------------------------------
# Default
# ------------------------------------------------------------
.PHONY: all
all: deps db ingest_graph ingest_runbooks ingest_docs

# ------------------------------------------------------------
# Python deps
# ------------------------------------------------------------
.PHONY: deps
deps:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

# ------------------------------------------------------------
# Clean  (DB only — Neo4j data lives in AuraDB)
# ------------------------------------------------------------
.PHONY: clean
clean:
	@echo "Cleaning local artifacts..."
	rm -f $(DB_PATH)

# ------------------------------------------------------------
# Database setup
# ------------------------------------------------------------
.PHONY: db
db:
	@mkdir -p $(dir $(DB_PATH))
	@echo "Initializing SQLite schema..."
	sqlite3 $(DB_PATH) < $(SQL_DIR)/created_tables.sql
	@echo "Seeding dataset..."
	sqlite3 $(DB_PATH) < $(SQL_DIR)/seed_reliability_data.sql
	@echo "Database ready."

# ------------------------------------------------------------
# Ingest telemetry graph → Neo4j (replaces old FAISS evidence index)
# ------------------------------------------------------------
.PHONY: ingest_graph
ingest_graph:
	@echo "Ingesting reliability graph into Neo4j..."
	$(PYTHON) -c "\
from src.RAG_chatbot.graph_model import ingest_reliability_graph_to_neo4j; \
from src.config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE; \
n, e = ingest_reliability_graph_to_neo4j('$(DB_PATH)', NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE); \
print(f'Done: {n} nodes, {e} edges ingested.')"

# ------------------------------------------------------------
# Ingest runbooks → Neo4j vector index
# ------------------------------------------------------------
.PHONY: ingest_runbooks
ingest_runbooks:
	@echo "Indexing runbooks into Neo4j..."
	$(PYTHON) -m src.RAG_build.ingest_runbooks \
		--runbooks_dir $(RUNBOOKS_DIR)

# ------------------------------------------------------------
# Ingest vendor docs → Neo4j vector index
# ------------------------------------------------------------
.PHONY: ingest_docs
ingest_docs:
	@echo "Indexing vendor docs into Neo4j..."
	$(PYTHON) -m src.RAG_build.ingest_vendor_docs

# ------------------------------------------------------------
# Tests
# ------------------------------------------------------------
.PHONY: test test_router test_retrieval test_e2e

# Run all three evaluation suites
test:
	@echo "Running full evaluation suite..."
	@set -a; [ -f .env ] && . ./.env || true; set +a; \
	$(PYTHON) -m pytest src/tests/test_vendor_corpus.py -v

# Run only router accuracy test
test_router:
	@set -a; [ -f .env ] && . ./.env || true; set +a; \
	$(PYTHON) -m pytest src/tests/test_vendor_corpus.py::test_router_accuracy -v

# Run only retrieval quality test
test_retrieval:
	@set -a; [ -f .env ] && . ./.env || true; set +a; \
	$(PYTHON) -m pytest src/tests/test_vendor_corpus.py::test_retrieval_quality -v

# Run only end-to-end LLM-as-judge test
test_e2e:
	@set -a; [ -f .env ] && . ./.env || true; set +a; \
	$(PYTHON) -m pytest src/tests/test_vendor_corpus.py::test_e2e_answer_quality -v

# Run standalone (no pytest, no LangSmith — prints to stdout)
test_local:
	@set -a; [ -f .env ] && . ./.env || true; set +a; \
	$(PYTHON) src/tests/test_vendor_corpus.py

# ------------------------------------------------------------
# Streamlit app
# ------------------------------------------------------------
.PHONY: app
app:
	@echo "Starting Streamlit app..."
	@set -a; [ -f .env ] && . ./.env || true; set +a; \
	$(PYTHON) -m streamlit run src/app.py
