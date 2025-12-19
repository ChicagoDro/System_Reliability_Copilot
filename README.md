```markdown
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
* **Incident Severity Breakdown**: Visual distribution of incidents by severity.
* **MTTR Analysis**: Mean Time To Recovery trends (planned).

### 2. Platform Health
* **Failing Resources**: Top failing jobs, pipelines, or infrastructure components.
* **Run History**: Cross-platform execution timeline (Airflow, dbt, K8s, Databricks).
* **SLA Breaches**: Analysis of jobs exceeding promised completion times or historical baselines.
* **Zombie Resources**: Active resources with no recent runs (planned).

### 3. Observability
* **Error Log Volume**: Spike detection and "Signature" analysis of repetitive logs.
* **Metric Anomalies**: Detection of data drops (e.g., 0 rows) or latency spikes.

### 4. Cost & Efficiency
* **Cloud Cost Overview**: Daily spend tracking, week-over-week trends, and top spender identification.
* **Cost of Downtime**: Estimated financial impact of outages (planned).
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

* **Source:** Official Databricks, Snowflake, Kubernetes, and Airflow documentation.
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
* `sql/seed_reliability_data.sql` (Unified Master Dataset)

### Key Tables

| Table | Description |
| --- | --- |
| `platform` | Cloud/Data platforms (AWS, Databricks, Snowflake, K8s, Airflow, dbt) |
| `environment` | Deployment envs (Prod, Stage, Dev) |
| `resource` | Jobs, tables, buckets, pipelines, services |
| `run` | Execution history, status, and duration |
| `incident` | Outages, alerts, and tickets |
| `log_record` | System logs and error traces |
| `metric_point` | Time-series metrics (Cost, Row Counts, Latency) |

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
git clone [https://github.com/ChicagoDro/AI-Portfolio](https://github.com/ChicagoDro/AI-Portfolio)
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

## Running the System (Unified Pipeline)

### Available Targets

* `make all` – **Recommended**: Builds DB, Ingests Evidence, Runbooks, & Docs, then starts App.
* `make db` – Rebuild & seed SQLite database.
* `make evidence` – Build Telemetry (Graph) index.
* `make runbooks` – Build Runbooks index.
* `make docs_index` – Build Unified Vendor Docs index.
* `make app` – Launch Streamlit UI.
* `make clean` – Remove all artifacts and indexes.

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
  ingest_vendor_docs.py     # Unified Web Scraper -> Vector index
  reports/
    registry.py             # Report definitions
    recent_incidents.py     # Incident report logic
    failing_resources.py    # Resource health report logic
    run_history.py          # Execution timeline logic
    sla_breaches.py         # Performance regression logic
    log_patterns.py         # Error signature logic
    metric_anomalies.py     # Data quality logic
    cost_overview.py        # Cloud spend logic

```

---

## Why This Matters (Portfolio Value)

This project demonstrates how to build **SRE-grade AI tools** that:

* Are **deterministic** (reports) instead of probabilistic (chat).
* Separate **facts** (telemetry) from **policy** (runbooks).
* Support **multi-hop reasoning** (GraphRAG) across interconnected infrastructure.
* Earn trust from engineering teams by citing sources (`[Runbook]`, `[Docs]`).

> **Chat-first copilots guess the problem. Reliability copilots show the data and cite the fix.**

---

# 🏗️ Production Architecture Proposal

This section outlines how to transition from the current "Seed Data" approach to a live production integration.

## 1. High-Level Data Flow

Instead of hardcoded SQL inserts, we introduce a **Collector Layer**. This layer runs on a schedule (e.g., every 5-15 minutes), fetches raw metadata, normalizes it, and upserts it into the Copilot database.

**The Golden Rule:** *Do not build agents into the pipelines.* (i.e., do not force developers to add `copilot.track()` to their Python code). Instead, rely on **Observer Patterns** (APIs, System Tables, Logs) to be non-intrusive.

## 2. Platform Integration Strategy

Here is how we map real-world signals to our schema:

### 🧱 Databricks (The Heavy Lifter)

* **Resources & Runs:** Query **System Tables** (`system.lakeflow.jobs`, `system.compute.clusters`) or poll the **Jobs API 2.1**.
* **Cost:** Query `system.billing.usage` for precise DBU attribution per job.
* **Logs:** Do NOT ingest all logs (too expensive). Instead, query the **Driver Logs** via API only upon failure, or subscribe to **Audit Logs** (`system.access.audit`) for permission/state changes.
* **Data Quality:** Hook into **Delta Live Tables (DLT)** event logs or **Databricks Lakehouse Monitoring** tables.

### ❄️ Snowflake

* **Runs & Cost:** Query `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY` and `QUERY_HISTORY`.
* **Data Quality:** Since Snowflake doesn't natively "push" DQ failures, we can parse **dbt test results** (see below) or ingest from a DQ tool (Monte Carlo, Soda) via API.

### ☸️ Kubernetes (Services)

* **Crash/Health:** Run a lightweight **K8s Informer/Watcher** (Python script) in the cluster. It watches for `Pod` events (OOMKilled, CrashLoopBackOff) and maps them to `Run` failures.
* **Logs:** Integrate with the existing Log Aggregator (Datadog/Splunk/CloudWatch). The Copilot calls the **Log Search API** specifically for the time window of a failed deployment.

### 💨 Airflow

* **Runs:** Poll the **Airflow REST API** (`/dags/{dag_id}/dagRuns`) or query the Airflow Metadata DB (Postgres) directly (faster).
* **Ingestion Errors:** Parse `task_instance` tables for failure reasons.

### 🛠️ dbt (Transformations)

* **Runs & Tests:** Parse the `run_results.json` and `manifest.json` artifacts generated by dbt Cloud or Core. These contain precise pass/fail states for tests and models.

## 3. The "Missing Link": User Configuration UI

You cannot automate everything. Some business context exists only in human heads. You need a simple **Streamlit Admin UI** (or a YAML config repo) for:

1. **SLA Definitions:**
* *Problem:* An API tells you a job took 50 minutes. It *doesn't* tell you if that's bad.
* *UI Need:* A form to set `Max Runtime`, `Freshness SLA` (e.g., "Must land by 8 AM"), and `Business Priority` (P0/P1) for critical resources.


2. **Incident Mapping:**
* *Problem:* How do we know which PagerDuty service maps to which Databricks Job?
* *UI Need:* A "Service Registry" to map `pagerduty_service_id` <--> `copilot_resource_id`.


3. **Owner Attribution:**
* *Problem:* Cloud tags are often messy or missing.
* *UI Need:* An override table to assign "Team Ownership" to resources found in the wild.



## 4. Integration Summary Table

| Copilot Entity | Primary Source Strategy | Fallback / UI Input |
| --- | --- | --- |
| **Resource** | **Discovery:** Scan Databricks Jobs API, K8s Services, Airflow DAG bags. | **Manual:** User tags "Critical Assets" in Admin UI. |
| **Run** | **Pull:** System Tables (DBX/Snow), REST API (Airflow). | **Push:** Webhook endpoint for custom scripts. |
| **Incident** | **Webhook:** PagerDuty / OpsGenie / ServiceNow outgoing webhooks. | **Manual:** "Create Incident" button in Copilot. |
| **Logs** | **Just-in-Time:** Fetch logs *only* for failed run IDs via Aggregator API. | **None:** Storing all logs is anti-pattern. |
| **Cost** | **Billing Tables:** `system.billing` (DBX), `USAGE` schemas (Snow). | **Manual:** Fixed daily costs for K8s services. |

```

```