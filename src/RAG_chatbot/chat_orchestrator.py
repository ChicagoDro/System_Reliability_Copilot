# src/chat_orchestrator.py
"""
Chat Orchestrator — LLM-based routing with a full LCEL pipeline.
Traces every step automatically via LangSmith when LANGCHAIN_TRACING_V2=true.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from langchain_community.vectorstores import Neo4jVector
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough

from src.config import (
    LLM_PROVIDER,
    get_chat_model_name,
    get_embed_model_name,
    DEFAULT_TEMPERATURE,
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    NEO4J_VENDOR_DOCS_INDEX,
    NEO4J_RUNBOOKS_INDEX,
    DOCS_RETRIEVER_K,
    RUNBOOKS_RETRIEVER_K,
)
from src.RAG_chatbot.graph_retriever import GraphRAGRetriever, _graph_node_to_doc

# ---------------------------------------------------------------------------
# Embedding factory
# ---------------------------------------------------------------------------

def _get_embeddings():
    provider = (LLM_PROVIDER or "openai").lower()
    model_name = get_embed_model_name()
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model_name)
    if provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model=model_name)
    raise ValueError(f"Unsupported LLM_PROVIDER for embeddings: {provider}")

# ---------------------------------------------------------------------------
# Neo4j vector retrievers
# ---------------------------------------------------------------------------

class Neo4jVectorRetriever:
    """Wraps a Neo4jVector index. Lazy-loads on first use."""

    def __init__(self, index_name: str, node_label: str) -> None:
        self.index_name = index_name
        self.node_label = node_label
        self._vs: Optional[Neo4jVector] = None
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                self._load()
                self._available = self._vs is not None
            except Exception:
                self._available = False
        return bool(self._available)

    def _load(self) -> None:
        if self._vs is not None:
            return
        self._vs = Neo4jVector.from_existing_index(
            embedding=_get_embeddings(),
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
            index_name=self.index_name,
            node_label=self.node_label,
            text_node_property="text",
            embedding_node_property="embedding",
        )

    def retrieve(self, query: str, k: int = 4) -> List[Document]:
        if not self.is_available():
            return []
        return self._vs.similarity_search(query, k=k)


class DatabricksDocsRetriever(Neo4jVectorRetriever):
    def __init__(self) -> None:
        super().__init__(NEO4J_VENDOR_DOCS_INDEX, "VendorDoc")


class RunbookRetriever(Neo4jVectorRetriever):
    def __init__(self) -> None:
        super().__init__(NEO4J_RUNBOOKS_INDEX, "Runbook")

# ---------------------------------------------------------------------------
# Source formatting helpers
# ---------------------------------------------------------------------------

def _extract_doc_sources(docs: List[Document]) -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    seen: set = set()
    for d in docs:
        meta = d.metadata or {}
        if meta.get("doc_type") != "runbook":
            url = meta.get("url") or meta.get("source_url") or meta.get("source")
            title = meta.get("title") or "Docs"
            if url and url not in seen:
                seen.add(url)
                results.append((title, url))
        else:
            chunk_id = meta.get("chunk_id", "unknown")
            if chunk_id not in seen:
                seen.add(chunk_id)
                platform = meta.get("platform_id", "General")
                topic = meta.get("topic", "Info")
                results.append((f"[Runbook] {platform.upper()}: {topic} (ID: {chunk_id})", "internal"))
    return results


def _append_sources_to_answer(answer_text: str, all_docs: List[Document]) -> str:
    pairs = _extract_doc_sources(all_docs)
    if not pairs:
        return answer_text
    lines = ["", "Sources:"]
    for title, url in pairs:
        lines.append(f"- {title}" if url == "internal" else f"- {title} — {url}")
    return answer_text.rstrip() + "\n" + "\n".join(lines) + "\n"

# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def get_llm(temperature: float = DEFAULT_TEMPERATURE):
    provider = (LLM_PROVIDER or "openai").lower()
    model_name = get_chat_model_name()
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_name, temperature=temperature)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

# ---------------------------------------------------------------------------
# Router prompt + decision type
# ---------------------------------------------------------------------------

ROUTER_PROMPT = PromptTemplate.from_template(
    """You are a routing classifier for a System Reliability Copilot. Return JSON only — no markdown, no explanation.

You have three retrieval backends:
- graph: A knowledge graph containing telemetry (job runs, incidents, metrics), ownership (team/oncall assignments),
  change history (deployments, config changes, schema modifications), and performance baselines.
- vendor_docs: A vector store with official platform documentation for Databricks, Snowflake, Kubernetes,
  Airflow, AWS EC2, dbt, and SRE principles. Use this for conceptual/reference questions.
- runbooks: A vector store with internal operational procedures, mitigation steps, and on-call playbooks.

Routing rules:
- graph: ownership ("who owns"), change history ("what changed"), telemetry ("how many failed", job/run data),
  baselines ("is this normal"), entity-specific queries (job_id=, run_id=, warehouse_id=, etc.)
- vendor_docs: "how does X work", "what is", "how do I configure", platform concepts, limits, best practices
- runbooks: "how to fix", mitigation steps, operational procedures, "what should I do when", alert responses
- Multiple backends may be true. When in doubt, set graph=true — telemetry is always useful.

Also classify the intent to enable specialized graph handlers:
- intent: one of ["global_aggregate", "global_topn", "ownership", "change_history", "baseline_check",
  "usage_overview", "other"]
- entity_type: one of ["job", "run", "incident", "service", "pod", "table", "database", "dag",
  "resource", "warehouse", "compute", null]

Examples:
- "How many jobs failed this week?" -> {{"intent": "global_aggregate", "entity_type": "job", "use_graph": true, "use_vendor_docs": false, "use_runbooks": false}}
- "Who owns the payment gateway service?" -> {{"intent": "ownership", "entity_type": "service", "use_graph": true, "use_vendor_docs": false, "use_runbooks": false}}
- "What changed on the nightly ETL job recently?" -> {{"intent": "change_history", "entity_type": "job", "use_graph": true, "use_vendor_docs": false, "use_runbooks": false}}
- "Is this latency spike normal for p95?" -> {{"intent": "baseline_check", "entity_type": "service", "use_graph": true, "use_vendor_docs": false, "use_runbooks": false}}
- "How do I configure autoscaling in Databricks?" -> {{"intent": "other", "entity_type": "compute", "use_graph": false, "use_vendor_docs": true, "use_runbooks": false}}
- "How do I fix an OOMKilled pod?" -> {{"intent": "other", "entity_type": "pod", "use_graph": false, "use_vendor_docs": true, "use_runbooks": true}}
- "The payment job is failing — who do I contact and how do I fix it?" -> {{"intent": "ownership", "entity_type": "job", "use_graph": true, "use_vendor_docs": false, "use_runbooks": true}}
- "Summarize system health" -> {{"intent": "usage_overview", "entity_type": null, "use_graph": true, "use_vendor_docs": false, "use_runbooks": false}}

Question: {question}
Return JSON with keys: intent, entity_type, use_graph, use_vendor_docs, use_runbooks.
"""
)


@dataclass
class RouterDecision:
    intent: str
    entity_type: Optional[str]
    use_graph: bool
    use_vendor_docs: bool
    use_runbooks: bool

# ---------------------------------------------------------------------------
# Answer prompt
# ---------------------------------------------------------------------------

ASSISTANT_SYSTEM_PROMPT = """You are a Data Reliability Copilot with deep operational context.
You answer questions using FIVE distinct sources of truth:

1. TELEMETRY: Real-world data about jobs, runs, and costs (the "what happened").
2. VENDOR DOCS: Official documentation on how platforms work (the "theory").
3. RUNBOOKS: Internal operational procedures and fix instructions (the "playbook").
4. OWNERSHIP: Team assignments, oncall rotations, and escalation policies (the "who").
5. CHANGE HISTORY: Recent deployments, config changes, and schema modifications (the "when").
6. BASELINES: Historical performance norms and SLA targets (the "is this normal").

Rules:
- For "who owns" questions: Prioritize OWNERSHIP data (team, slack channel, PagerDuty).
- For "what changed" questions: Look for CHANGE HISTORY nodes showing recent modifications.
- For "is this normal" questions: Compare current metrics against BASELINES (p50, p95).
- For "how to fix" questions: Use RUNBOOKS for procedures.
- For "why did it fail" questions: Use TELEMETRY + CHANGE HISTORY correlation.
- Always cite which source you're using (e.g., "[Ownership]", "[Change History]", "[Baseline]").
- If context is missing, admit it. Do not hallucinate procedures or ownership.
"""

ASSISTANT_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", ASSISTANT_SYSTEM_PROMPT),
    ("human", "CONTEXT:\n{context}\n\nQUESTION:\n{question}"),
])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_graph_explanation(node_ids: List[str], retriever: GraphRAGRetriever) -> str:
    if not node_ids:
        return "No graph nodes were retrieved."
    lines = [f"Retrieved {len(node_ids)} graph nodes (showing up to 15):"]
    for nid in node_ids[:15]:
        n = retriever.get_node(nid)
        if not n:
            lines.append(f"- {nid} | (missing node)")
            continue
        ntype = n.get("node_type", "unknown")
        attrs: dict = {}
        try:
            attrs = json.loads(n.get("attrs_json") or "{}")
        except Exception:
            pass
        name = attrs.get("job_name") or attrs.get("name") or n.get("title") or nid
        lines.append(f"- {nid} | type={ntype} | name={name}")
    if len(node_ids) > 15:
        lines.append(f"... ({len(node_ids) - 15} more)")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ChatResult:
    answer: str
    context_docs: Optional[List[Document]] = None
    graph_explanation: Optional[str] = None
    llm_prompt: Optional[str] = None
    llm_context: Optional[str] = None


@dataclass(frozen=True)
class PromptPackItem:
    key: str
    title: str
    prompt: str

# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

class ReliabilityAssistant:
    def __init__(
        self,
        graph_retriever: GraphRAGRetriever,
        docs_retriever: Optional[Neo4jVectorRetriever] = None,
        runbooks_retriever: Optional[Neo4jVectorRetriever] = None,
    ) -> None:
        self.graph_retriever = graph_retriever
        self.docs_retriever = docs_retriever
        self.runbooks_retriever = runbooks_retriever
        self.llm = get_llm()
        self._pipeline = self._build_pipeline()

    @classmethod
    def from_local(cls) -> "ReliabilityAssistant":
        graph = GraphRAGRetriever.from_local_index()
        docs = DatabricksDocsRetriever()
        rbooks = RunbookRetriever()
        return cls(
            graph_retriever=graph,
            docs_retriever=docs if docs.is_available() else None,
            runbooks_retriever=rbooks if rbooks.is_available() else None,
        )

    # ------------------------------------------------------------------
    # LCEL pipeline construction
    # ------------------------------------------------------------------

    def _build_pipeline(self):
        # Step 1: Router — LLM decides intent + which backends to hit
        _route = (
            ROUTER_PROMPT
            | get_llm(temperature=0)
            | StrOutputParser()
            | RunnableLambda(self._parse_router)
        ).with_config(run_name="router")

        # Step 2: Retrieval — conditional fan-out across graph + vector stores
        _retrieve = RunnableLambda(self._retrieve_backends).with_config(run_name="retrieve")

        # Step 3: Context builder — formats retrieved docs into a prompt string
        _build_ctx = RunnableLambda(self._build_context).with_config(run_name="build_context")

        # Step 4: Generation — answer LLM call
        _generate = (
            ASSISTANT_PROMPT_TEMPLATE | self.llm | StrOutputParser()
        ).with_config(run_name="generate")

        # General pipeline for questions that need full retrieval + generation
        _general = (
            RunnablePassthrough.assign(retrieved=_retrieve)
            | RunnablePassthrough.assign(context=_build_ctx)
            | RunnablePassthrough.assign(answer_raw=_generate)
            | RunnableLambda(self._finalize_result)
        ).with_config(run_name="general_pipeline")

        # Only truly deterministic intents short-circuit (no LLM needed).
        # ownership / change_history / baseline_check flow through _general so the
        # LLM sees the full graph context; seed_node_types in _retrieve_backends
        # biases the graph search toward the relevant node type.
        _branch = RunnableBranch(
            (
                lambda x: x["decision"].intent == "usage_overview",
                RunnableLambda(lambda x: self._answer_global_usage_overview()),
            ),
            (
                lambda x: x["decision"].intent == "global_aggregate"
                          and bool(x["decision"].entity_type),
                RunnableLambda(lambda x: self._answer_global_aggregate(x["decision"].entity_type)),
            ),
            _general,  # all other intents — full retrieval + LLM generation
        ).with_config(run_name="intent_branch")

        return (
            RunnablePassthrough.assign(decision=_route)
            | _branch
        ).with_config(run_name="reliability_assistant")

    # ------------------------------------------------------------------
    # Pipeline step implementations
    # ------------------------------------------------------------------

    def _parse_router(self, raw: str) -> RouterDecision:
        try:
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)
            return RouterDecision(
                intent=data.get("intent", "other"),
                entity_type=data.get("entity_type"),
                use_graph=bool(data.get("use_graph", True)),
                use_vendor_docs=bool(data.get("use_vendor_docs", False)),
                use_runbooks=bool(data.get("use_runbooks", False)),
            )
        except Exception as e:
            print(f"Warning: Router parse failed ({e}), defaulting to graph-only.")
            return RouterDecision(
                intent="other", entity_type=None,
                use_graph=True, use_vendor_docs=False, use_runbooks=False,
            )

    # Intent → seed node types for focused graph retrieval.
    # The BFS expansion still traverses all types, so related context is preserved.
    _INTENT_SEED_TYPES = {
        "ownership":      {"owner"},
        "change_history": {"change"},
        "baseline_check": {"baseline"},
    }

    def _retrieve_backends(self, inputs: dict) -> dict:
        question = inputs["question"]
        decision: RouterDecision = inputs["decision"]
        focus = inputs.get("focus")

        telemetry_docs: List[Document] = []
        node_ids: List[str] = []

        if decision.use_graph:
            seed_node_types = self._INTENT_SEED_TYPES.get(decision.intent)
            telemetry_docs, node_ids = self.graph_retriever.get_subgraph_for_query(
                query=question, seed_limit=5, depth=3, max_nodes=60,
                seed_node_types=seed_node_types,
            )
            if focus and focus.get("entity_id") and focus.get("entity_type"):
                forced_id = f"{focus['entity_type']}::{focus['entity_id']}"
                if forced_id not in node_ids:
                    node = self.graph_retriever.get_node(forced_id)
                    if node:
                        telemetry_docs.insert(0, _graph_node_to_doc(forced_id, node))
                        node_ids.insert(0, forced_id)

        vendor_docs: List[Document] = (
            self.docs_retriever.retrieve(question, k=DOCS_RETRIEVER_K)
            if decision.use_vendor_docs and self.docs_retriever else []
        )
        runbook_docs: List[Document] = (
            self.runbooks_retriever.retrieve(question, k=RUNBOOKS_RETRIEVER_K)
            if decision.use_runbooks and self.runbooks_retriever else []
        )

        return {
            "telemetry_docs": telemetry_docs,
            "node_ids": node_ids,
            "vendor_docs": vendor_docs,
            "runbook_docs": runbook_docs,
        }

    def _build_context(self, inputs: dict) -> str:
        r = inputs["retrieved"]
        ctx  = self._render_docs(r["telemetry_docs"], "TELEMETRY CONTEXT")
        ctx += self._render_docs(r["runbook_docs"], "RUNBOOK CONTEXT (Internal Procedures)")
        ctx += self._render_docs(r["vendor_docs"], "VENDOR DOCS")
        return ctx

    def _finalize_result(self, inputs: dict) -> ChatResult:
        r = inputs["retrieved"]
        all_retrieved = r["vendor_docs"] + r["runbook_docs"]
        answer_text = _append_sources_to_answer(inputs["answer_raw"], all_retrieved)

        graph_explanation = build_graph_explanation(r["node_ids"], self.graph_retriever)
        if inputs.get("focus"):
            graph_explanation += "\n\n[focus]\n" + json.dumps(inputs["focus"], indent=2)

        context_str = inputs["context"]
        return ChatResult(
            answer=answer_text,
            context_docs=r["telemetry_docs"] + all_retrieved,
            graph_explanation=graph_explanation,
            llm_prompt=ASSISTANT_SYSTEM_PROMPT + "\n\n" + context_str + "\n\nQUESTION:\n" + inputs["question"],
            llm_context=context_str,
        )

    # ------------------------------------------------------------------
    # Specialized graph-native handlers
    # ------------------------------------------------------------------

    def _answer_global_aggregate(self, entity_type: str) -> ChatResult:
        count = self.graph_retriever.count_nodes_by_type(entity_type.lower())
        return ChatResult(
            answer=f"There are {count} {entity_type}(s) in the dataset.",
            graph_explanation=f"[deterministic] Counted nodes of type '{entity_type}'.",
        )

    def _answer_global_usage_overview(self) -> ChatResult:
        return ChatResult(answer="System overview not implemented in lite mode.", graph_explanation="N/A")

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_docs(self, docs: List[Document], section_title: str) -> str:
        if not docs:
            return ""
        parts = [f"=== {section_title} ==="]
        for i, d in enumerate(docs, start=1):
            meta = d.metadata or {}
            if meta.get("doc_type") == "runbook":
                header = f"[{i}] RUNBOOK: {meta.get('topic', 'Topic')} (ID: {meta.get('chunk_id')})"
            else:
                header = f"[{i}] DOCS: {meta.get('title', 'Untitled')}"
            parts.append(f"{header}\n{d.page_content.strip()}")
        return "\n\n".join(parts) + "\n\n"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_prompt_pack(self, items: List[PromptPackItem], focus: Optional[dict] = None) -> List[ChatResult]:
        return [self.answer(it.prompt, focus=focus) for it in items]

    def answer(self, question: str, focus: Optional[dict] = None) -> ChatResult:
        return self._pipeline.invoke({"question": question, "focus": focus})
