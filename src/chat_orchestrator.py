# src/chat_orchestrator.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.config import (
    LLM_PROVIDER,
    get_chat_model_name,
    get_embed_model_name,
    DEFAULT_TEMPERATURE,
    VENDOR_DOCS_INDEX_PATH,
    DOCS_RETRIEVER_K,
)
from src.graph_retriever import GraphRAGRetriever

# ---------------------------------------------------------------------------
# Config Constants
# ---------------------------------------------------------------------------

# Path to the runbooks index (matches Makefile 'runbooks_demo' target)
RUNBOOKS_FAISS_INDEX_PATH = "indexes/reliability_runbooks_demo"
RUNBOOKS_RETRIEVER_K = 4


# ---------------------------------------------------------------------------
# Routing Heuristics
# ---------------------------------------------------------------------------

_DOCS_INTENT_PATTERNS = [
    r"\bwhat is\b",
    r"\bwhat does\b",
    r"\bhow do i\b",
    r"\bhow to\b",
    r"\bhow does\b",
    r"\bconfigure\b",
    r"\bsetting(s)?\b",
    r"\bbest practice(s)?\b",
    r"\blimit(s)?\b",
]

_DOCS_TOPIC_KEYWORDS = [
    "compute", "cluster", "autoscaling", "auto scaling", "node type",
    "instance type", "spot", "on-demand", "photon", "warehouse",
    "serverless", "dbu", "pools", "policies", "job cluster", "driver"
]

_OPS_INTENT_PATTERNS = [
    r"\bfix\b",
    r"\bmitigat",
    r"\bresolve\b",
    r"\bpage\b",
    r"\bcontact\b",
    r"\bowner\b",
    r"\bsla\b",
    r"\bseverity\b",
    r"\bprocedure\b",
    r"\brunbook\b",
    r"\balert\b",
    r"\bescalat",
    r"\bdeadlock\b",
    r"\btimeout\b",
    r"\bfailure\b",
]

def _looks_like_docs_question(q: str) -> bool:
    """Checks if the user is asking about general platform capabilities."""
    ql = q.lower().strip()
    if any(k in ql for k in _DOCS_TOPIC_KEYWORDS):
        return True
    return any(re.search(p, ql) for p in _DOCS_INTENT_PATTERNS)

def _looks_like_operational_question(q: str) -> bool:
    """Checks if the user is asking for operational fixes, ownership, or procedures."""
    ql = q.lower().strip()
    return any(re.search(p, ql) for p in _OPS_INTENT_PATTERNS)

def _has_entity_anchor(q: str) -> bool:
    ql = q.lower()
    return any(
        token in ql
        for token in [
            "job_id=", "run_id=", "query_id=", "warehouse_id=",
            "cluster_id=", "user_id=", "compute_type="
        ]
    )


# ---------------------------------------------------------------------------
# Embedding Factory
# ---------------------------------------------------------------------------

def _get_embeddings_for_retrieval():
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
# Retrievers
# ---------------------------------------------------------------------------

class BaseFaissRetriever:
    def __init__(self, index_path: str):
        self.index_path = index_path
        self._vs = None
        self._available = None

    def is_available(self) -> bool:
        if self._available is None:
            # Simple check if directory exists
            import os
            self._available = os.path.isdir(self.index_path)
        return self._available

    def _load(self):
        if self._vs is not None:
            return
        if not self.is_available():
            return
        
        embeddings = _get_embeddings_for_retrieval()
        try:
            self._vs = FAISS.load_local(
                self.index_path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
        except Exception as e:
            print(f"Warning: Failed to load index at {self.index_path}: {e}")
            self._available = False

    def retrieve(self, query: str, k: int = 4) -> List[Document]:
        if not self.is_available():
            return []
        self._load()
        if not self._vs:
            return []
        return self._vs.similarity_search(query, k=k)


class DatabricksDocsRetriever(BaseFaissRetriever):
    """Retrieves from public Databricks documentation."""
    pass


class RunbookRetriever(BaseFaissRetriever):
    """Retrieves from internal operational runbooks (markdown)."""
    pass


# ---------------------------------------------------------------------------
# Source Formatting Helpers
# ---------------------------------------------------------------------------

def _extract_doc_sources(docs: List[Document]) -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    seen = set()
    for d in docs:
        meta = d.metadata or {}
        # Handle Vendor Docs
        if meta.get("doc_type") != "runbook":
            url = meta.get("url") or meta.get("source_url")
            title = meta.get("title") or "Databricks Docs"
            if url and url not in seen:
                seen.add(url)
                results.append((title, url))
        # Handle Runbooks
        else:
            chunk_id = meta.get("chunk_id", "unknown")
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            
            # Format: Runbook (Platform) - Topic
            platform = meta.get("platform_id", "General")
            topic = meta.get("topic", "Info")
            display = f"[Runbook] {platform.upper()}: {topic} (ID: {chunk_id})"
            results.append((display, "internal"))
            
    return results


def _append_sources_to_answer(answer_text: str, all_docs: List[Document]) -> str:
    pairs = _extract_doc_sources(all_docs)
    if not pairs:
        return answer_text

    lines = ["", "Sources:"]
    for title, url in pairs:
        if url == "internal":
            lines.append(f"- {title}")
        else:
            lines.append(f"- {title} — {url}")
            
    return answer_text.rstrip() + "\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# LLM Factory
# ---------------------------------------------------------------------------

def get_llm():
    provider = (LLM_PROVIDER or "openai").lower()
    model_name = get_chat_model_name()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_name, temperature=DEFAULT_TEMPERATURE)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_name, temperature=DEFAULT_TEMPERATURE)

    if provider == "grok":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model_name, temperature=DEFAULT_TEMPERATURE)

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

ASSISTANT_SYSTEM_PROMPT = """You are a Data Reliability Copilot.
You answer questions using 3 distinct sources of context:

1. TELEMETRY: Real-world data about jobs, runs, and costs (the "what happened").
2. VENDOR DOCS: Official documentation on how the platform works (the "theory").
3. RUNBOOKS: Internal operational procedures, ownership, and fix instructions (the "playbook").

Rules:
- Prioritize RUNBOOKS for "how to fix", "who owns", or "SLA" questions.
- Use TELEMETRY to confirm if the issue actually occurred.
- Use VENDOR DOCS to explain technical concepts or limits.
- If context is missing, admit it. Do not hallucinate runbook procedures.
"""

ASSISTANT_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", ASSISTANT_SYSTEM_PROMPT),
        ("human", "CONTEXT:\n{context}\n\nQUESTION:\n{question}"),
    ]
)

QUESTION_CLASSIFIER_PROMPT = PromptTemplate.from_template(
    """You are a classifier. Return JSON only.

Classify the user's question into:
- intent: one of ["global_aggregate", "global_topn", "other"]
- entity_type: one of ["job", "warehouse", "user", "query", "run", null]

Guidance:
- "How many X are there?" -> global_aggregate, entity_type=X
- "Top N most expensive jobs" -> global_topn, entity_type=job
- Otherwise -> other, entity_type=null

Question: {question}

Return JSON with keys intent and entity_type.
"""
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _looks_like_job_count_question(q: str) -> bool:
    ql = q.lower()
    return ("how many jobs" in ql) or ("number of jobs" in ql)

def _looks_like_usage_overview_question(q: str) -> bool:
    ql = q.lower()
    return ("tell me about my databricks usage" in ql) or ("summarize my databricks usage" in ql)

def _looks_like_jobs_optimization_question(q: str) -> bool:
    ql = q.lower()
    return ("jobs need optimizing" in ql) or ("which jobs should i optimize" in ql)

def _extract_top_n(q: str, default: int = 3) -> int:
    m = re.search(r"\btop\s+(\d+)\b", q.lower())
    if m:
        return int(m.group(1))
    return default

def build_graph_explanation(node_ids: List[str], retriever: GraphRAGRetriever) -> str:
    if not node_ids:
        return "No graph nodes were retrieved."

    nodes = retriever.adj.nodes
    lines = [f"Retrieved {len(node_ids)} graph nodes (showing up to 12):"]

    for nid in node_ids[:12]:
        n = nodes.get(nid)
        if not n:
            lines.append(f"- {nid} | (missing node)")
            continue
        ntype = getattr(n, "type", "unknown")
        props = getattr(n, "properties", {}) or {}
        name = props.get("job_name") or props.get("user_name") or props.get("job_id") or ""
        lines.append(f"- {nid} | type={ntype} | name={name}")

    if len(node_ids) > 12:
        lines.append(f"... ({len(node_ids) - 12} more)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Result Types
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
        docs_retriever: Optional[DatabricksDocsRetriever] = None,
        runbooks_retriever: Optional[RunbookRetriever] = None,
    ) -> None:
        self.graph_retriever = graph_retriever
        self.docs_retriever = docs_retriever
        self.runbooks_retriever = runbooks_retriever
        self.llm = get_llm()
        self.chain = ASSISTANT_PROMPT_TEMPLATE | self.llm | StrOutputParser()
        self.classifier_chain = QUESTION_CLASSIFIER_PROMPT | self.llm | StrOutputParser()

    @classmethod
    def from_local(cls) -> "ReliabilityAssistant":
        # 1. Graph (Telemetry)
        graph = GraphRAGRetriever.from_local_index()
        
        # 2. Vendor Docs
        docs = DatabricksDocsRetriever(VENDOR_DOCS_INDEX_PATH)
        docs_r = docs if docs.is_available() else None
        
        # 3. Runbooks (Internal)
        rbooks = RunbookRetriever(RUNBOOKS_FAISS_INDEX_PATH)
        rbooks_r = rbooks if rbooks.is_available() else None
        
        return cls(graph_retriever=graph, docs_retriever=docs_r, runbooks_retriever=rbooks_r)

    def _classify_question(self, question: str) -> dict:
        raw = self.classifier_chain.invoke({"question": question})
        try:
            return json.loads(raw)
        except Exception:
            return {"intent": "other", "entity_type": None}

    # -----------------------------------------------------------------------
    # Deterministic Aggregations (kept largely same)
    # -----------------------------------------------------------------------
    
    def _compute_job_costs(self) -> Dict[str, Dict[str, float]]:
        # (Simplified for brevity, logic matches original)
        nodes = self.graph_retriever.adj.nodes
        nbrs = self.graph_retriever.adj.neighbors
        job_costs: Dict[str, Dict[str, float]] = {}

        for node_id, node in nodes.items():
            if getattr(node, "type", None) != "compute_usage":
                continue
            props = getattr(node, "properties", {}) or {}
            cost = float(props.get("cost_usd", 0.0))
            
            # Simple traversal: usage -> run -> job
            job_run_id = next((nb for nb in nbrs.get(node_id, set()) 
                               if getattr(nodes.get(nb), "type", None) == "job_run"), None)
            if not job_run_id: continue
            
            job_id = next((nb for nb in nbrs.get(job_run_id, set()) 
                           if getattr(nodes.get(nb), "type", None) == "job"), None)
            if not job_id: continue

            if job_id not in job_costs:
                job_name = (getattr(nodes[job_id], "properties", {}).get("job_name") or job_id)
                job_costs[job_id] = {"name": job_name, "cost": 0.0}
            job_costs[job_id]["cost"] += cost
        return job_costs

    def _answer_global_aggregate(self, entity_type: str) -> ChatResult:
        entity_type = entity_type.lower()
        count = sum(1 for n in self.graph_retriever.adj.nodes.values() 
                    if getattr(n, "type", None) == entity_type)
        return ChatResult(
            answer=f"There are {count} {entity_type}(s) in the dataset.",
            graph_explanation=f"[deterministic] Counted nodes of type '{entity_type}'.",
        )

    def _answer_global_usage_overview(self) -> ChatResult:
        counts: Dict[str, int] = {}
        for node in self.graph_retriever.adj.nodes.values():
            t = getattr(node, "type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        lines = ["Here’s a high-level overview of your Databricks usage dataset:"]
        for k in sorted(counts.keys()):
            lines.append(f"- {k}: {counts[k]}")
        return ChatResult(
            answer="\n".join(lines),
            graph_explanation="[deterministic] Summarized entity counts by node.type",
        )

    def _answer_global_topn_jobs(self, top_n: int) -> ChatResult:
        job_costs = self._compute_job_costs()
        ranked = sorted(job_costs.items(), key=lambda kv: kv[1]["cost"], reverse=True)[:top_n]
        lines = [f"Top {top_n} most expensive jobs:"]
        for job_id, info in ranked:
            lines.append(f"- {info['name']} (job_id={job_id}): ${info['cost']:.2f}")
        return ChatResult(
            answer="\n".join(lines),
            graph_explanation="[deterministic] Aggregated cost_usd",
        )

    def _answer_jobs_needing_optimization(self) -> ChatResult:
        return self._answer_global_topn_jobs(5)

    # -----------------------------------------------------------------------
    # Context Rendering
    # -----------------------------------------------------------------------

    def _render_docs(self, docs: List[Document], section_title: str) -> str:
        if not docs:
            return ""
        parts = [f"=== {section_title} ==="]
        for i, d in enumerate(docs, start=1):
            meta = d.metadata or {}
            
            # Formatting header info
            if meta.get("doc_type") == "runbook":
                header = f"[{i}] RUNBOOK: {meta.get('topic', 'Topic')} (Platform: {meta.get('platform_id')})"
            else:
                header = f"[{i}] DOCS: {meta.get('title', 'Untitled')}"
                
            parts.append(f"{header}\n{d.page_content.strip()}")
        return "\n\n".join(parts) + "\n\n"

    def run_prompt_pack(self, items: List[PromptPackItem], focus: Optional[dict] = None) -> List[ChatResult]:
        out: List[ChatResult] = []
        for it in items:
            out.append(self.answer(it.prompt, focus=focus))
        return out

    # -----------------------------------------------------------------------
    # Main Answer Logic
    # -----------------------------------------------------------------------

    def answer(self, question: str, focus: Optional[dict] = None) -> ChatResult:
        # 1. Deterministic Shortcuts
        if _looks_like_job_count_question(question):
            return self._answer_global_aggregate("job")
        if _looks_like_usage_overview_question(question):
            return self._answer_global_usage_overview()
        if _looks_like_jobs_optimization_question(question):
            return self._answer_jobs_needing_optimization()

        classification = self._classify_question(question)
        if classification.get("intent") == "global_aggregate":
            return self._answer_global_aggregate(classification["entity_type"])
        if classification.get("intent") == "global_topn" and classification["entity_type"] == "job":
            return self._answer_global_topn_jobs(_extract_top_n(question))

        # 2. Retrieve Contexts
        
        # A) Telemetry (Graph)
        telemetry_docs, node_ids = self.graph_retriever.get_subgraph_for_query(
            query=question, anchor_k=4, max_hops=2, max_nodes=40
        )
        
        # B) Vendor Docs (optional)
        vendor_docs: List[Document] = []
        if self.docs_retriever and (_looks_like_docs_question(question) or not _has_entity_anchor(question)):
            vendor_docs = self.docs_retriever.retrieve(question, k=DOCS_RETRIEVER_K)
            
        # C) Runbooks (optional)
        runbook_docs: List[Document] = []
        if self.runbooks_retriever and _looks_like_operational_question(question):
            runbook_docs = self.runbooks_retriever.retrieve(question, k=RUNBOOKS_RETRIEVER_K)

        # 3. Build Prompt Context
        context_str = self._render_docs(telemetry_docs, "TELEMETRY CONTEXT")
        context_str += self._render_docs(runbook_docs, "RUNBOOK CONTEXT (Internal Procedures)")
        context_str += self._render_docs(vendor_docs, "VENDOR DOCS (Databricks)")
        
        # 4. Generate Explanation
        graph_explanation = build_graph_explanation(node_ids=node_ids, retriever=self.graph_retriever)
        if focus:
            graph_explanation += "\n\n[focus]\n" + json.dumps(focus, indent=2)

        # 5. Invoke LLM
        llm_prompt_text = (
            ASSISTANT_SYSTEM_PROMPT 
            + "\n\n" + context_str 
            + "\n\nQUESTION:\n" + question
        )
        answer_text = self.chain.invoke({"context": context_str, "question": question})

        # 6. Append Sources
        all_retrieved = vendor_docs + runbook_docs
        answer_text = _append_sources_to_answer(answer_text, all_retrieved)

        return ChatResult(
            answer=answer_text,
            context_docs=telemetry_docs + all_retrieved,
            graph_explanation=graph_explanation,
            llm_prompt=llm_prompt_text,
            llm_context=context_str,
        )