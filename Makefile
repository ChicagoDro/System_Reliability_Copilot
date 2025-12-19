# ------------------------------------------------------------
# Makefile — Data Reliability Copilot (SQLite, self-contained)
# ------------------------------------------------------------

PYTHON := python
DB_PATH := data/reliability.db
SQL_DIR := sql
INDEX_DIR := indexes
RUNBOOKS_DIR := src/runbooks

EMBEDDINGS_PROVIDER ?= openai
EMBEDDINGS_MODEL ?=

# ------------------------------------------------------------
# Default
# ------------------------------------------------------------
.PHONY: all
all: deps db_demo evidence_demo docs_index runbooks_demo

# ------------------------------------------------------------
# Python deps
# ------------------------------------------------------------
.PHONY: deps
deps:
	$(PYTHON) -m pip install -r requirements.txt

# ------------------------------------------------------------
# Clean
# ------------------------------------------------------------
.PHONY: clean
clean:
	@echo "🧹 Cleaning indexes and SQLite database..."
	rm -rf \
		$(INDEX_DIR)/reliability_evidence_lite \
		$(INDEX_DIR)/reliability_evidence_demo \
		$(INDEX_DIR)/reliability_runbooks_lite \
		$(INDEX_DIR)/reliability_runbooks_demo \
		$(INDEX_DIR)/vendor_docs_databricks

	rm -f $(DB_PATH)

# ------------------------------------------------------------
# Database setup
# ------------------------------------------------------------
.PHONY: db_lite
db_lite:
	@mkdir -p $(dir $(DB_PATH))
	@echo "🗄️  Initializing SQLite schema: $(DB_PATH)"
	sqlite3 $(DB_PATH) < $(SQL_DIR)/created_tables.sql
	@echo "🌱 Seeding LITE dataset: $(DB_PATH)"
	sqlite3 $(DB_PATH) < $(SQL_DIR)/seed_reliability_data_lite.sql
	@echo "✔️  Seeded (LITE)"

.PHONY: db_demo
db_demo:
	@mkdir -p $(dir $(DB_PATH))
	@echo "🗄️  Initializing SQLite schema: $(DB_PATH)"
	sqlite3 $(DB_PATH) < $(SQL_DIR)/created_tables.sql
	@echo "🌱 Seeding DEMO dataset: $(DB_PATH)"
	sqlite3 $(DB_PATH) < $(SQL_DIR)/seed_reliability_data_demo.sql
	@echo "✔️  Seeded (DEMO)"

# ------------------------------------------------------------
# Evidence indexes (RAG over reliability data)
# ------------------------------------------------------------
.PHONY: evidence_lite
evidence_lite:
	@echo "📦 Building EVIDENCE index (LITE)"
	EMBEDDINGS_PROVIDER=$(EMBEDDINGS_PROVIDER) EMBEDDINGS_MODEL=$(EMBEDDINGS_MODEL) \
	$(PYTHON) -m src.ingest_embed_index \
		--db-path $(DB_PATH) \
		--index-dir $(INDEX_DIR) \
		--index-name reliability_evidence_lite \
		--mode lite

.PHONY: evidence_demo
evidence_demo:
	@echo "📦 Building EVIDENCE index (DEMO)"
	EMBEDDINGS_PROVIDER=$(EMBEDDINGS_PROVIDER) EMBEDDINGS_MODEL=$(EMBEDDINGS_MODEL) \
	$(PYTHON) -m src.ingest_embed_index \
		--db-path $(DB_PATH) \
		--index-dir $(INDEX_DIR) \
		--index-name reliability_evidence_demo \
		--mode demo

# ------------------------------------------------------------
# Runbooks indexes
# ------------------------------------------------------------
.PHONY: runbooks_lite
runbooks_lite:
	@echo "📚 Building RUNBOOKS index (LITE)"
	EMBEDDINGS_PROVIDER=$(EMBEDDINGS_PROVIDER) EMBEDDINGS_MODEL=$(EMBEDDINGS_MODEL) \
	$(PYTHON) -m src.ingest_runbooks \
		--runbooks_dir $(RUNBOOKS_DIR) \
		--index_dir $(INDEX_DIR) \
		--index_name reliability_runbooks_lite \
		--mode lite

.PHONY: runbooks_demo
runbooks_demo:
	@echo "📚 Building RUNBOOKS index (DEMO)"
	EMBEDDINGS_PROVIDER=$(EMBEDDINGS_PROVIDER) EMBEDDINGS_MODEL=$(EMBEDDINGS_MODEL) \
	$(PYTHON) -m src.ingest_runbooks \
		--runbooks_dir $(RUNBOOKS_DIR) \
		--index_dir $(INDEX_DIR) \
		--index_name reliability_runbooks_demo \
		--mode demo

# ------------------------------------------------------------
# Streamlit app
# ------------------------------------------------------------
.PHONY: app
app:
	@echo "🚀 Starting Streamlit app..."
	@# Load .env if present so OPENAI_API_KEY and friends are available.
	@set -a; [ -f .env ] && . ./.env || true; set +a; \
	$(PYTHON) -m streamlit run src/app.py

# ------------------------------------------------------------
# Vendor Docs Index (Databricks)
# ------------------------------------------------------------
.PHONY: docs_index
docs_index:
	@echo "📚 Building VENDOR DOCS index (Databricks)"
	EMBEDDINGS_PROVIDER=$(EMBEDDINGS_PROVIDER) EMBEDDINGS_MODEL=$(EMBEDDINGS_MODEL) \
	$(PYTHON) -m src.ingest_databricks_docs