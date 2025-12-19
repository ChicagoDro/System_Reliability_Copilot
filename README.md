Here is the updated `README.md` for the **System Reliability Copilot**. It reflects the broader scope, the new tri-corpus architecture (Telemetry + Docs + Runbooks), and the updated Reliability schema.

# System Reliability Copilot

**Pete Tamisin** – Technical GTM Leader • AI & Data Engineering Architect • Builder & Teacher
Chicago, IL

* 20+ years designing data & AI platforms (Director at Capital One, ex-Databricks, 2x Series A startup exits, x-Siemens, x-Motorola)
* Focused on **modern data platforms**, **context-aware RAG systems**, and **enterprise GenAI adoption**
* Passionate about **teaching** and helping teams ship real-world AI systems

📧 Email: `pete@tamisin.com`
🔗 LinkedIn: [https://www.linkedin.com/in/peter-tamisin-50a3233a/](https://www.linkedin.com/in/peter-tamisin-50a3233a/)

---

## Overview

**System Reliability Copilot** is a deterministic, report-driven AI assistant for analyzing incidents, platform health, observability, and operational risk across complex data systems.

Originally focused on Databricks cost optimization, this project has evolved into a broader **Reliability Copilot** designed to help SREs and Platform Engineers answer critical questions: *What is broken? Why did it fail? How do we fix it? Who owns it?*

Unlike chat-first copilots, this project is **report-driven and deterministic**:

* SQL defines the facts (incidents, runs, logs)
* Reports define the context (Incident Response, Platform Health)
* User selections define scope
* LLMs explain results and suggest fixes using **Runbooks** and **Vendor Docs**

The result is an **enterprise-grade AI copilot** that is explainable, debuggable, and trustworthy.

---

## Core Design Principle

> **Don’t let the model guess what the user meant.**
> Use deterministic reports to define intent, and use the LLM to explain the result with context.

This project deliberately avoids “blank chat box” UX. Instead:

* **Reports** define the operational context (e.g., "Recent Incidents")
* **Clicks** define the specific entity to investigate
* **Prompts** are deterministic and repeatable
* **LLMs** provide narrative, root-cause hypotheses, and next actions

---

## Deterministic Reports (Not Chat Guessing)

Each report is powered by explicit SQL and semantic meaning. The system is organized into **Operational Pillars**:

### 1. Incident Response

* **Recent Incidents**: Active outages, severity breakdown, and status timeline.
* **MTTR Analysis**: Mean Time To Recovery trends (planned).

### 2. Platform Health

* **Failing Resources**: Top failing jobs, pipelines, or infrastructure components.
* **Run History**: Recent execution outcomes and duration trends.
* **SLA Breaches**: Jobs exceeding promised completion times (planned).

### 3. Observability

* **Error Log Volume**: Spike detection in error logs.
* **Metric Anomalies**: Deviation from baseline performance metrics (planned).

### 4. Cost & Efficiency

* **Cost of Downtime**: Estimated financial impact of outages.
* **Idle Resources**: Provisioned but unused infrastructure (planned).

Reports are the **interface**.
AI is the **commentary layer**.

---

## Deterministic Action Chips (Key Differentiator)

A core design principle is that **AI actions are deterministic, contextual, and intentional**.

Rather than free-form prompting, the UI presents **action chips** that are:

* **Deterministic** – each chip maps to a fixed prompt template
* **Context-aware** – prompts are parameterized by the selected entity (incident, resource, run)
* **Stable** – chip identity and ordering do not change
* **Explainable** – users can inspect the prompt executed

### Chip Taxonomy

Action chips are organized into four operational lanes:

* **Understand** – What is this resource? Who owns it? What is the impact?
* **Diagnose** – Why did it fail? What do the logs say? What changed?
* **Optimize** – How do I prevent this? What is the fix?
* **Monitor** – How do I validate the fix? What alert should I add?

---

## Report → Selection → Prompt → Answer

```text
┌─────────────────────────┐
│ Report (SQL + semantics)│
│ Incident Table / Chart  │
└───────────┬─────────────┘
            │ click / select
            ▼
┌─────────────────────────┐
│ Selection Context       │
│ entity_type + entity_id │
└───────────┬─────────────┘
            │ deterministic template
            ▼
┌─────────────────────────┐
│ Prompt Builder          │
│ “Draft Post-Mortem…”    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ LLM Commentary Answer   │
│ + Sources (Runbooks)    │
└─────────────────────────┘

```

---

## Tri-Corpus Architecture: Telemetry, Docs, & Runbooks

The System Reliability Copilot uniquely combines **three** distinct sources of truth to answer questions. It doesn't just "chat" with one index; it routes intent to the right knowledge base.

### 1. Telemetry Corpus (The "What")

* **Source:** SQLite database (`incident`, `run`, `resource`, `log_record`).
* **Format:** Knowledge Graph (GraphRAG).
* **Role:** Answers "What happened?", "Who is affected?", "When did it fail?".

### 2. Vendor Docs Corpus (The "Theory")

* **Source:** Official Databricks (or other vendor) documentation.
* **Format:** Vector Index (FAISS).
* **Role:** Answers "What does this error code mean?", "How does autoscaling work?".

### 3. Runbooks Corpus (The "Playbook")

* **Source:** Internal markdown runbooks (`src/runbooks/`).
* **Format:** Vector Index (FAISS).
* **Role:** Answers "How do I fix this?", "Who do I page?", "What is the SLA?".

### Intelligent Routing

The `ReliabilityAssistant` automatically assembles context from all three sources:

> "The **Telemetry** shows Job A failed at 10:00 AM. **Vendor Docs** explain that `Error 429` is a rate limit. **Runbooks** prescribe scaling the cluster to `2x-large` as the fix."

---

## Dataset Overview

All data lives in a local **SQLite database**: `data/reliability.db`.

Generated from:

* `sql/created_tables.sql`
* `sql/seed_reliability_data_demo.sql`

### Key Tables

| Table | Description |
| --- | --- |
| `platform` | Cloud/Data platforms (AWS, Databricks, Snowflake) |
| `environment` | Deployment envs (Prod, Stage, Dev) |
| `resource` | Jobs, tables, buckets, pipelines |
| `run` | Execution history and status |
| `incident` | Outages, alerts, and tickets |
| `log_record` | System logs and error traces |
| `metric_point` | Time-series metrics (CPU, Latency) |

---

## Architecture Overview

```text
SQLite Reliability DB
   ↓ SQL
Reports Registry
   ↓
Streamlit Dashboard
   - Visualization Pane
   - Commentary Pane (LLM)
   - Action Chips (Diagnose/Fix)
   ↓
Prompt Builder + Context Assembler
   ↓
GraphRAG (Telemetry)
   +
Docs RAG (Vendor Docs)
   +
Runbooks RAG (Internal Procedures)
   ↓
LLM

```

---

## Setup & Installation

### 1. Clone

```bash
git clone https://github.com/ChicagoDro/AI-Portfolio
cd AI-Portfolio

```

### 2. Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate

```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

```

### 4. Environment Variables

Create `.env`:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

```

---

## Running the System (Makefile)

### Available Targets

* `make db_demo` – build & seed SQLite database with demo data
* `make evidence_demo` – build Telemetry (Graph) index
* `make runbooks_demo` – build Runbooks index
* `make docs_index` – build Vendor Docs index
* `make app` – launch Streamlit UI
* `make all` – build everything (DB + 3 Indexes + App)
* `make clean` – remove generated artifacts

### First Run

```bash
make all

```

Streamlit will launch at: `http://localhost:8501`

---

## Project Structure

```text
src/
  app.py                    # Streamlit UI
  chat_orchestrator.py      # Tri-corpus routing + prompts
  graph_model.py            # Nodes + edges definition
  graph_retriever.py        # GraphRAG traversal for Telemetry
  ingest_reliability_domain.py # SQLite -> Graph ingestion
  ingest_runbooks.py        # Markdown -> Vector index
  ingest_databricks_docs.py # Web -> Vector index
  reports/
    registry.py             # Report definitions
    recent_incidents.py     # Incident report logic
    failing_resources.py    # Resource health report logic

```

---

## Why This Matters (Portfolio Value)

This project demonstrates how to build **SRE-grade AI tools** that:

* Are **deterministic** (reports) instead of probabilistic (chat).
* Separate **facts** (telemetry) from **policy** (runbooks).
* Support **multi-hop reasoning** (GraphRAG) across interconnected infrastructure.
* Earn trust from engineering teams by citing sources (`[Runbook]`, `[Docs]`).

> **Chat-first copilots guess the problem.
> Reliability copilots show the data and cite the fix.**

---

## Roadmap

### Pillar-Based Reports (Planned)

* **Observability:** Metric anomaly detection.
* **Resilience:** Chaos engineering experiment results.
* **Cost:** "Cost of Downtime" estimation.

### Agent-Based Capabilities (Future)

* **Auto-Triage:** Automatically classify incoming incidents based on runbook matches.
* **Remediation Agents:** Propose specific API calls or Terraform changes to fix identified issues.

### Evaluation

* **Regression Testing:** Deterministic evaluation of answer quality against known incident scenarios.