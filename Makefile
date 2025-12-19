# Makefile — System Reliability Copilot
# Single unified pipeline.

PYTHON := python
DB_PATH := data/reliability.db
SQL_DIR := sql
INDEX_DIR := indexes
RUNBOOKS_DIR := src/runbooks

# ------------------------------------------------------------
# Default
# ------------------------------------------------------------
.PHONY: all
all: deps db evidence runbooks docs_index

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
	@echo "🧹 Cleaning artifacts..."
	rm -rf $(INDEX_DIR)/reliability_evidence
	rm -rf $(INDEX_DIR)/reliability_runbooks
	rm -rf $(INDEX_DIR)/databricks_docs
	rm -f $(DB_PATH)

# ------------------------------------------------------------
# Database setup
# ------------------------------------------------------------
.PHONY: db
db:
	@mkdir -p $(dir $(DB_PATH))
	@echo "🗄️  Initializing SQLite schema..."
	sqlite3 $(DB_PATH) < $(SQL_DIR)/created_tables.sql
	@echo "🌱 Seeding dataset..."
	sqlite3 $(DB_PATH) < $(SQL_DIR)/seed_reliability_data.sql
	@echo "✔️  Database ready."

# ------------------------------------------------------------
# Evidence index (Graph/Telemetry)
# ------------------------------------------------------------
.PHONY: evidence
evidence:
	@echo "📦 Building EVIDENCE index..."
	EMBEDDINGS_PROVIDER=$(EMBEDDINGS_PROVIDER) EMBEDDINGS_MODEL=$(EMBEDDINGS_MODEL) \
	$(PYTHON) -m src.ingest_embed_index \
		--db-path $(DB_PATH) \
		--index-dir $(INDEX_DIR) \
		--index_name reliability_evidence

# ------------------------------------------------------------
# Runbooks index
# ------------------------------------------------------------
.PHONY: runbooks
runbooks:
	@echo "📚 Building RUNBOOKS index..."
	EMBEDDINGS_PROVIDER=$(EMBEDDINGS_PROVIDER) EMBEDDINGS_MODEL=$(EMBEDDINGS_MODEL) \
	$(PYTHON) -m src.ingest_runbooks \
		--runbooks_dir $(RUNBOOKS_DIR) \
		--index_dir $(INDEX_DIR) \
		--index_name reliability_runbooks

# ------------------------------------------------------------
# Vendor Docs Index
# ------------------------------------------------------------
.PHONY: docs_index
docs_index:
	@echo "📚 Building VENDOR DOCS index..."
	EMBEDDINGS_PROVIDER=$(EMBEDDINGS_PROVIDER) EMBEDDINGS_MODEL=$(EMBEDDINGS_MODEL) \
	$(PYTHON) -m src.ingest_vendor_docs

# ------------------------------------------------------------
# Streamlit app
# ------------------------------------------------------------
.PHONY: app
app:
	@echo "🚀 Starting Streamlit app..."
	@set -a; [ -f .env ] && . ./.env || true; set +a; \
	$(PYTHON) -m streamlit run src/app.py