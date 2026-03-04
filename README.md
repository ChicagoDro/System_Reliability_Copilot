# System Reliability Copilot

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

> **Don't let the model guess what the user meant.**
> Use deterministic reports to define intent, and use the LLM to explain the result with context.

This project deliberately avoids "blank chat box" UX. Instead:

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
* **Service Health (Golden Signals)**: Latency, Traffic, Errors, and Saturation for infrastructure.

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
│ "Draft Post-Mortem…"    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ LLM Commentary Answer   │
│ + Sources (Runbooks)    │
└─────────────────────────┘
```

---

## Neo4j: The Database of Choice

The System Reliability Copilot is built on **Neo4j AuraDB** as its unified data backend — replacing separate FAISS vector stores and an in-memory graph with a single, purpose-built graph + vector database.

### Why Neo4j for a Reliability Copilot?

Reliability data is **inherently a graph problem**. Infrastructure isn't a collection of isolated rows — it's a web of relationships:

```
Job → uses → ComputeConfig
Job → owned_by → Team (Slack channel, PagerDuty rotation)
Job → incurred_cost → CostRecord
Incident → affected → Resource → has_baseline → MetricNorm
Change → modified → Resource ← run_of_resource ← FailedRun
```

A relational database forces you to JOIN across many tables to reconstruct this context. A vector database gives you semantic similarity but loses the relationships entirely. Neo4j gives you both at once.

### Three Problems, One Database

| Problem | Traditional Approach | Neo4j Approach |
|---|---|---|
| Telemetry graph traversal | In-memory dict + BFS | Native Cypher path queries `(n)-[*0..3]-(m)` |
| Vendor docs similarity search | Separate FAISS index | Native vector index on `VendorDoc` nodes |
| Runbook retrieval | Separate FAISS index | Native vector index on `Runbook` nodes |

### Specific Capabilities That Matter Here

**1. Graph-native ownership and escalation chains**
When an incident fires, the copilot traverses: `Incident → affected → Resource → owned_by → Owner` in a single Cypher query. No joins. No cross-index lookups.

**2. Change correlation**
"Why did this job fail?" often means finding what changed right before the failure. Cypher makes this a natural traversal: `FailedRun → run_of_resource → Resource ← changed ← ChangeRecord`.

**3. Hybrid graph + vector queries**
Neo4j 5.x allows vector similarity search directly on graph nodes, enabling queries like: *"Find runbooks semantically similar to this error message, then traverse to the resources and teams they apply to."* This is not possible with FAISS + a separate graph.

**4. LLM-based routing maps cleanly to query strategy**
The `chat_orchestrator` uses an LLM router to decide between `use_graph`, `use_vendor_docs`, and `use_runbooks`. In Neo4j, all three are just different Cypher + vector index patterns against the same connection — no infrastructure switching.

**5. Production scalability**
AuraDB is a fully managed cloud service. No FAISS files to re-index, no in-memory graphs to rebuild on startup. The same graph that powers a demo scales to millions of nodes for production telemetry.

### LangChain Integration

Neo4j integrates natively with the LangChain ecosystem used throughout this project:

* `Neo4jVector` — drop-in replacement for `FAISS` with identical `similarity_search()` API
* `Neo4jGraph` — structured graph access for Cypher-based retrieval
* Full LangSmith tracing across all Neo4j-backed retrieval steps

---

## Tri-Corpus Architecture: Telemetry, Docs, & Runbooks

The System Reliability Copilot combines **three** distinct sources of truth — all stored in Neo4j — and routes questions to the right knowledge base using an LLM router.

### 1. Telemetry Graph (The "What")

* **Source:** SQLite → ingested into Neo4j as `ReliabilityNode` nodes with typed relationships.
* **Format:** Native property graph with full-text index (`reliabilityFullText`).
* **Role:** Answers "What happened?", "Who is affected?", "What changed?", "Is this normal?".

### 2. Vendor Docs (The "Theory")

* **Source:** Official Databricks, Snowflake, Kubernetes, Airflow, dbt, and SRE documentation.
* **Format:** Neo4j vector index on `VendorDoc` nodes.
* **Role:** Answers "What does this error mean?", "How does autoscaling work?".

### 3. Runbooks (The "Playbook")

* **Source:** Internal markdown runbooks (`src/runbooks/`).
* **Format:** Neo4j vector index on `Runbook` nodes.
* **Role:** Answers "How do I fix this?", "Who do I page?", "What is the SLA?".

### LLM-Based Intelligent Routing

Instead of brittle keyword matching, the `ReliabilityAssistant` uses an LLM router to decide which backends to query for each question:

```
Question → LLM Router → RouterDecision {use_graph, use_vendor_docs, use_runbooks}
                ↓
        RunnableBranch (LCEL)
        ├── ownership   → Cypher graph traversal
        ├── change_history → Cypher graph traversal
        ├── baseline_check → Cypher graph traversal
        └── general → Neo4j graph + vector retrieval → LLM answer
```

> "The **Telemetry graph** shows Job A failed at 10:00 AM. **Vendor Docs** explain that `Error 429` is a rate limit. **Runbooks** prescribe scaling the cluster to `2x-large` as the fix."

---

## LangSmith Observability

Every step of the pipeline is traced end-to-end via **LangSmith**:

```
reliability_assistant
├── router              ← LLM routing decision (latency, tokens)
└── intent_branch
    └── general_pipeline
        ├── retrieve    ← Neo4j graph + vector retrieval
        ├── build_context
        └── generate    ← LLM answer generation
```

Enable tracing by setting `LANGCHAIN_TRACING_V2=true` in your `.env`.

---

## Dataset Overview

All operational data is seeded into **SQLite** (`data/reliability.db`) and ingested into Neo4j.

**SQL source files:** `src/setup/`
* `created_tables.sql` — schema definition
* `seed_reliability_data.sql` — demo dataset

### Key Tables → Graph Node Types

| SQLite Table | Neo4j Node Type | Description |
|---|---|---|
| `platform` | (metadata) | Cloud/Data platforms |
| `resource` | `ReliabilityNode {node_type: "resource"}` | Jobs, pipelines, services |
| `run` | `ReliabilityNode {node_type: "run"}` | Execution history |
| `incident` | `ReliabilityNode {node_type: "incident"}` | Outages and alerts |
| `log_record` | (via metrics) | System logs |
| `metric_point` | `ReliabilityNode {node_type: "metric"}` | Time-series metrics |
| `resource_owner` | `ReliabilityNode {node_type: "owner"}` | Team ownership |
| `resource_change` | `ReliabilityNode {node_type: "change"}` | Deployments, config changes |
| `resource_baseline` | `ReliabilityNode {node_type: "baseline"}` | Performance norms |
| `sla_policy` | `ReliabilityNode {node_type: "sla"}` | SLA definitions |

---

## Architecture Overview

```text
SQLite Reliability DB
   ↓ ingest_reliability_graph_to_neo4j()
Neo4j AuraDB
   ├── ReliabilityNode graph  (telemetry, ownership, change history, baselines)
   ├── VendorDoc vector index (Databricks, Snowflake, K8s, Airflow, dbt docs)
   └── Runbook vector index   (internal operational playbooks)
        ↓
LLM Router (LCEL)
   ↓
ReliabilityAssistant (chat_orchestrator.py)
   ↓
Streamlit Dashboard
   ├── Reports (SQL → SQLite)
   ├── Action Chips (deterministic prompts)
   └── Commentary Pane (LLM answer + cited sources)
```

---

## Project Structure

```text
src/
├── app.py                        # Streamlit UI entrypoint
├── config.py                     # Shared config and env vars
│
├── RAG_chatbot/                  # Core retrieval + reasoning layer
│   ├── chat_orchestrator.py      # LCEL pipeline, LLM router, answer generation
│   ├── graph_model.py            # SQLite → Neo4j graph ingestion
│   ├── graph_retriever.py        # Neo4j Cypher-based graph retrieval
│   ├── investigation_engine.py   # Investigation agent logic
│   └── prompts_deterministic.py  # Deterministic prompt packs (action chips)
│
├── RAG_build/                    # One-time index build scripts
│   ├── ingest_reliability_domain.py  # SQLite → RagDoc builder
│   ├── ingest_embed_index.py         # Legacy FAISS builder (reference)
│   ├── ingest_vendor_docs.py         # Web scraper → Neo4j VendorDoc index
│   └── ingest_runbooks.py            # Markdown → Neo4j Runbook index
│
├── setup/                        # Database initialization
│   ├── created_tables.sql
│   └── seed_reliability_data.sql
│
├── reports/                      # Streamlit report modules
│   ├── registry.py
│   ├── recent_incidents.py
│   ├── failing_resources.py
│   ├── run_history.py
│   ├── sla_breaches.py
│   ├── log_patterns.py
│   ├── metric_anomalies.py
│   ├── cost_overview.py
│   └── service_health.py
│
└── runbooks/                     # Internal operational runbooks (markdown)
```

---

## Setup & Installation

### 1. Clone

```bash
git clone https://github.com/ChicagoDro/System_Reliability_Copilot
cd System_Reliability_Copilot
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

Copy `.env.example` to `.env` and fill in your keys:

```env
# LLM
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here

# Neo4j AuraDB
NEO4J_URI=neo4j+s://<instance>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=neo4j

# LangSmith (optional but recommended)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_PROJECT=system-reliability-copilot
```

---

## Running the System

### Make Targets

| Target | Description |
|---|---|
| `make all` | Full pipeline: deps → db → Neo4j ingestion → app |
| `make db` | Rebuild and seed SQLite database |
| `make ingest_graph` | Ingest telemetry graph into Neo4j |
| `make ingest_runbooks` | Index runbooks into Neo4j vector store |
| `make ingest_docs` | Index vendor docs into Neo4j vector store |
| `make app` | Launch Streamlit UI |
| `make clean` | Remove local SQLite DB |

### First Run

```bash
make all
```

Streamlit will launch at: `http://localhost:8501`

---

## Why This Architecture?

This project demonstrates how to build **SRE-grade AI tools** that:

* Are **deterministic** (reports) instead of probabilistic (chat).
* Separate **facts** (telemetry) from **policy** (runbooks).
* Support **multi-hop reasoning** across interconnected infrastructure using Neo4j graph traversal.
* Use a **single database** for graph, full-text, and vector search — eliminating index sprawl.
* Earn trust from engineering teams by citing sources (`[Runbook]`, `[Docs]`, `[Ownership]`).

> **Chat-first copilots guess the problem. Reliability copilots show the data and cite the fix.**

---

# Production Architecture Proposal

This section outlines how to transition from the current demo dataset to live production integration.

## High-Level Data Flow

Instead of hardcoded SQL inserts, introduce a **Collector Layer** that runs on a schedule (every 5–15 minutes), fetches raw metadata from platform APIs, normalizes it, and upserts it directly into Neo4j.

**The Golden Rule:** *Do not build agents into the pipelines.* Rely on **Observer Patterns** (APIs, System Tables, Webhooks) to stay non-intrusive.

## Platform Integration Strategy

### Databricks
* **Resources & Runs:** Query System Tables (`system.lakeflow.jobs`, `system.compute.clusters`) or poll Jobs API 2.1.
* **Cost:** Query `system.billing.usage` for DBU attribution per job.
* **Logs:** Fetch Driver Logs via API only on failure; subscribe to Audit Logs for state changes.

### Snowflake
* **Runs & Cost:** Query `SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY` and `QUERY_HISTORY`.
* **Data Quality:** Parse dbt test results or integrate via Monte Carlo / Soda APIs.

### Kubernetes
* **Crash/Health:** Run a lightweight K8s Informer/Watcher watching for `OOMKilled`, `CrashLoopBackOff` pod events.
* **Logs:** Integrate with existing log aggregator (Datadog/Splunk) and fetch logs just-in-time for failed runs.

### Airflow
* **Runs:** Poll the Airflow REST API or query the metadata DB (Postgres) directly.

### dbt
* **Runs & Tests:** Parse `run_results.json` and `manifest.json` artifacts from dbt Cloud or Core.

## Integration Summary

| Copilot Entity | Primary Source | Fallback |
|---|---|---|
| **Resource** | Scan platform APIs (Databricks Jobs, K8s Services, Airflow DAGs) | Manual tag in Admin UI |
| **Run** | System Tables (DBX/Snow), REST API (Airflow) | Webhook endpoint |
| **Incident** | PagerDuty / OpsGenie / ServiceNow outgoing webhooks | Manual "Create Incident" |
| **Logs** | Just-in-time fetch for failed run IDs via log aggregator API | None (storing all logs is anti-pattern) |
| **Cost** | Billing tables (`system.billing`, Snowflake `USAGE`) | Fixed daily costs for K8s |
