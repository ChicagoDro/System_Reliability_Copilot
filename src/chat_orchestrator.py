# src/chat_orchestrator.py
"""
Enhanced Chat Orchestrator with support for ownership, change history, and baselines.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set

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
    RELIABILITY_RUNBOOKS_INDEX_PATH,
    RUNBOOKS_RETRIEVER_K
)
from src.graph_retriever import GraphRAGRetriever

# ---------------------------------------------------------------------------
# Routing Heuristics (Enhanced)
# ---------------------------------------------------------------------------

_DOCS_INTENT_PATTERNS = [
    r"\bwhat is\b", r"\bwhat does\b", r"\bhow do i\b", r"\bhow to\b",
    r"\bhow does\b", r"\bconfigure\b", r"\bsetting(s)?\b",
    r"\bbest practice(s)?\b", r"\blimit(s)?\b",
]

_DOCS_TOPIC_KEYWORDS = [
    "compute", "cluster", "autoscaling", "spot", "on-demand", "photon",
    "warehouse", "serverless", "dbu", "pools", "policies", "job cluster",
    "schema evolution", "auto loader", "delta live tables",
    "snowpipe", "time travel", "undrop", "clustering keys", "micro-partition",
    "credit usage", "cloud services",
    "pod", "container", "ingress", "latency", "throughput", "iops", 
    "load balancer", "vpc", "subnet", "firewall", "pvc", "eviction",
    "liveness", "readiness", "oomkilled", "crashloop",
    "sensor", "backfill", "xcom", "task instance", "incremental", "snapshot"
]

_OPS_INTENT_PATTERNS = [
    r"\bfix\b", r"\bmitigat", r"\bresolve\b", r"\bpage\b", r"\bcontact\b",
    r"\bowner\b", r"\bsla\b", r"\bseverity\b", r"\bprocedure\b",
    r"\brunbook\b", r"\balert\b", r"\bescalat\b", r"\bdeadlock\b",
    r"\btimeout\b", r"\bfailure\b", r"\bfix\b",
    r"\bscale\b", r"\brollback\b", r"\brestart\b", r"\bdrain\b", r"\bdeploy\b",
    r"\blog(s)?\b", r"\btrace(s)?\b", r"\bmetric(s)?\b"
]

# NEW: Patterns for ownership, change, and baseline queries
_OWNERSHIP_PATTERNS = [
    r"\bwho owns\b", r"\bowner\b", r"\boncall\b", r"\bresponsible\b",
    r"\bteam\b", r"\bslack channel\b", r"\bpagerduty\b", r"\bescalate\b"
]

_CHANGE_PATTERNS = [
    r"\bwhat changed\b", r"\brecent change(s)?\b", r"\bdeployment(s)?\b",
    r"\bconfig change\b", r"\bschema change\b", r"\bwhen did.*change\b",
    r"\bwho changed\b", r"\bbefore and after\b"
]

_BASELINE_PATTERNS = [
    r"\bis this normal\b", r"\busual(ly)?\b", r"\bbaseline\b", r"\baverage\b",
    r"\btypical(ly)?\b", r"\bhistorical\b", r"\bcompared to\b", r"\bp95\b", r"\bp50\b"
]

def _looks_like_docs_question(q: str) -> bool:
    ql = q.lower().strip()
    if any(k in ql for k in _DOCS_TOPIC_KEYWORDS):
        return True
    return any(re.search(p, ql) for p in _DOCS_INTENT_PATTERNS)

def _looks_like_operational_question(q: str) -> bool:
    ql = q.lower().strip()
    return any(re.search(p, ql) for p in _OPS_INTENT_PATTERNS)

def _looks_like_ownership_question(q: str) -> bool:
    ql = q.lower().strip()
    return any(re.search(p, ql) for p in _OWNERSHIP_PATTERNS)

def _looks_like_change_question(q: str) -> bool:
    ql = q.lower().strip()
    return any(re.search(p, ql) for p in _CHANGE_PATTERNS)

def _looks_like_baseline_question(q: str) -> bool:
    ql = q.lower().strip()
    return any(re.search(p, ql) for p in _BASELINE_PATTERNS)

def _has_entity_anchor(q: str) -> bool:
    ql = q.lower()
    return any(
        token in ql
        for token in [
            "job_id=", "run_id=", "query_id=", "warehouse_id=",
            "cluster_id=", "user_id=", "compute_type=", "incident_id=",
            "resource_id=", "dataset_id=", "rule_id=", "platform_id="
        ]
    )

def _looks_like_usage_overview_question(q: str) -> bool:
    ql = q.lower()
    keywords = [
        "system status", "system health", "platform overview", 
        "cost overview", "summarize usage", "platform health",
        "summarize my databricks usage"
    ]
    return any(k in ql for k in keywords)

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
    def __init__(self, index_path):
        self.index_path = index_path
        self._vs = None
        self._available = None

    def is_available(self) -> bool:
        if self._available is None:
            import os
            path_str = str(self.index_path)
            self._available = os.path.isdir(path_str)
        return self._available

    def _load(self):
        if self._vs is not None:
            return
        if not self.is_available():
            return
        
        embeddings = _get_embeddings_for_retrieval()
        try:
            self._vs = FAISS.load_local(
                str(self.index_path),
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
    """Retrieves from unified vendor documentation."""
    pass

class RunbookRetriever(BaseFaissRetriever):
    """Retrieves from internal operational runbooks."""
    pass

# ---------------------------------------------------------------------------
# Source Formatting Helpers
# ---------------------------------------------------------------------------

def _extract_doc_sources(docs: List[Document]) -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    seen = set()
    for d in docs:
        meta = d.metadata or {}
        if meta.get("doc_type") != "runbook":
            url = meta.get("url") or meta.get("source_url")
            title = meta.get("title") or "Docs"
            if url and url not in seen:
                seen.add(url)
                results.append((title, url))
        else:
            chunk_id = meta.get("chunk_id", "unknown")
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
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
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

# ---------------------------------------------------------------------------
# Prompts (Enhanced)
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

ASSISTANT_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", ASSISTANT_SYSTEM_PROMPT),
        ("human", "CONTEXT:\n{context}\n\nQUESTION:\n{question}"),
    ]
)

QUESTION_CLASSIFIER_PROMPT = PromptTemplate.from_template(
    """You are a classifier for a Reliability Copilot. Return JSON only.

Classify the user's question into:
- intent: one of ["global_aggregate", "global_topn", "ownership", "change_history", "baseline_check", "other"]
- entity_type: one of [
    "job", "run", "incident", "service", "pod", 
    "table", "database", "dag", "resource", "warehouse", "compute"
]

Examples:
- "How many jobs failed?" -> {{"intent": "global_aggregate", "entity_type": "job"}}
- "Who owns the payment gateway?" -> {{"intent": "ownership", "entity_type": "service"}}
- "What changed on res_job_nightly_fact recently?" -> {{"intent": "change_history", "entity_type": "job"}}
- "Is this latency spike normal?" -> {{"intent": "baseline_check", "entity_type": "service"}}
- "Show me the top 5 failing services" -> {{"intent": "global_topn", "entity_type": "service"}}

Question: {question}
Return JSON with keys intent and entity_type.
"""
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_graph_explanation(node_ids: List[str], retriever: GraphRAGRetriever) -> str:
    if not node_ids:
        return "No graph nodes were retrieved."
    nodes = retriever.adj.nodes
    lines = [f"Retrieved {len(node_ids)} graph nodes (showing up to 15):"]
    for nid in node_ids[:15]:
        n = nodes.get(nid)
        if not n:
            lines.append(f"- {nid} | (missing node)")
            continue
        ntype = getattr(n, "type", "unknown")
        props = getattr(n, "properties", {}) or {}
        name = props.get("job_name") or props.get("title") or props.get("name") or nid
        lines.append(f"- {nid} | type={ntype} | name={name}")
    if len(node_ids) > 15:
        lines.append(f"... ({len(node_ids) - 15} more)")
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
# Main Orchestrator (Enhanced)
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
        rbooks = RunbookRetriever(RELIABILITY_RUNBOOKS_INDEX_PATH)
        rbooks_r = rbooks if rbooks.is_available() else None
        
        return cls(graph_retriever=graph, docs_retriever=docs_r, runbooks_retriever=rbooks_r)
    
    def _classify_question(self, question: str) -> dict:
        try:
            raw = self.classifier_chain.invoke({"question": question})
            return json.loads(raw)
        except Exception:
            return {"intent": "other", "entity_type": None}

    def _answer_global_aggregate(self, entity_type: str) -> ChatResult:
        entity_type = entity_type.lower()
        count = sum(1 for n in self.graph_retriever.adj.nodes.values() 
                    if getattr(n, "type", "").lower() == entity_type 
                    or (getattr(n, "type", "") == "resource" and entity_type in getattr(n, "properties", {}).get("name", "").lower()))
        
        return ChatResult(
            answer=f"There are {count} {entity_type}(s) in the dataset.",
            graph_explanation=f"[deterministic] Counted nodes of type '{entity_type}'.",
        )

    def _answer_ownership_question(self, focus: Optional[dict] = None) -> ChatResult:
        """Handle 'who owns' questions by searching for owner nodes."""
        # Search for owner nodes
        owner_hits = self.graph_retriever.search("owner team oncall slack pagerduty", limit=10, node_types={"owner"})
        
        if not owner_hits and not focus:
            return ChatResult(answer="No ownership information found in the system.")
        
        # If focused on a specific resource, find its owner
        if focus and focus.get("entity_id"):
            resource_id = focus["entity_id"]
            # Look for edges from resource to owner
            resource_node = self.graph_retriever.get_node(f"resource::{resource_id}")
            if resource_node:
                neighbors = self.graph_retriever.neighbors(f"resource::{resource_id}")
                owner_neighbors = [n for n in neighbors if "owner::" in n.get("id", "")]
                if owner_neighbors:
                    owner_id = owner_neighbors[0]["id"]
                    owner_node = self.graph_retriever.get_node(owner_id)
                    if owner_node:
                        return ChatResult(
                            answer=f"[Ownership] {owner_node.get('text', 'Owner information found')}",
                            graph_explanation=f"Found owner node: {owner_id}"
                        )
        
        # Generic ownership answer
        owner_text = "\n\n".join([f"- {h.title}: {h.snippet}" for h in owner_hits[:5]])
        return ChatResult(
            answer=f"[Ownership] Found {len(owner_hits)} teams:\n\n{owner_text}",
            graph_explanation=f"Retrieved {len(owner_hits)} owner nodes"
        )

    def _answer_change_history_question(self, focus: Optional[dict] = None) -> ChatResult:
        """Handle 'what changed' questions by searching for change nodes."""
        change_hits = self.graph_retriever.search("change config deployment schema", limit=10, node_types={"change"})
        
        if not change_hits:
            return ChatResult(answer="No recent changes found in the system.")
        
        # Format changes chronologically
        change_text = "\n\n".join([
            f"- [{h.node_type}] {h.title}\n  {h.snippet[:200]}" 
            for h in change_hits[:5]
        ])
        
        return ChatResult(
            answer=f"[Change History] Found {len(change_hits)} recent changes:\n\n{change_text}",
            graph_explanation=f"Retrieved {len(change_hits)} change nodes"
        )

    def _answer_baseline_question(self, focus: Optional[dict] = None) -> ChatResult:
        """Handle 'is this normal' questions by comparing against baselines."""
        baseline_hits = self.graph_retriever.search("baseline p50 p95 average", limit=10, node_types={"baseline"})
        
        if not baseline_hits:
            return ChatResult(answer="No baseline data found for comparison.")
        
        baseline_text = "\n\n".join([
            f"- {h.title}: {h.snippet}" 
            for h in baseline_hits[:5]
        ])
        
        return ChatResult(
            answer=f"[Baseline] Historical norms:\n\n{baseline_text}\n\nCompare current metrics against these baselines.",
            graph_explanation=f"Retrieved {len(baseline_hits)} baseline nodes"
        )

    def _answer_global_usage_overview(self) -> ChatResult:
        return ChatResult(answer="System overview not implemented in lite mode.", graph_explanation="N/A")

    def _render_docs(self, docs: List[Document], section_title: str) -> str:
        if not docs: return ""
        parts = [f"=== {section_title} ==="]
        for i, d in enumerate(docs, start=1):
            meta = d.metadata or {}
            if meta.get("doc_type") == "runbook":
                header = f"[{i}] RUNBOOK: {meta.get('topic', 'Topic')} (ID: {meta.get('chunk_id')})"
            else:
                header = f"[{i}] DOCS: {meta.get('title', 'Untitled')}"
            parts.append(f"{header}\n{d.page_content.strip()}")
        return "\n\n".join(parts) + "\n\n"

    def run_prompt_pack(self, items: List[PromptPackItem], focus: Optional[dict] = None) -> List[ChatResult]:
        out: List[ChatResult] = []
        for it in items:
            out.append(self.answer(it.prompt, focus=focus))
        return out

    def answer(self, question: str, focus: Optional[dict] = None) -> ChatResult:
        # 1. Deterministic Shortcuts (Enhanced Classification)
        if _looks_like_usage_overview_question(question):
             return self._answer_global_usage_overview()

        classification = self._classify_question(question)
        intent = classification.get("intent")
        
        if intent == "global_aggregate" and classification.get("entity_type"):
            return self._answer_global_aggregate(classification["entity_type"])
        
        # NEW: Specialized handlers
        if intent == "ownership" or _looks_like_ownership_question(question):
            return self._answer_ownership_question(focus)
        
        if intent == "change_history" or _looks_like_change_question(question):
            return self._answer_change_history_question(focus)
        
        if intent == "baseline_check" or _looks_like_baseline_question(question):
            return self._answer_baseline_question(focus)

        # 2. Retrieve Contexts
        
        # A) Telemetry (Graph) - Force focus entity
        forced_seeds = []
        if focus and focus.get("entity_id") and focus.get("entity_type"):
            forced_id = f"{focus['entity_type']}::{focus['entity_id']}"
            forced_seeds.append(forced_id)

        telemetry_docs, node_ids = self.graph_retriever.get_subgraph_for_query(
            query=question, 
            seed_limit=5,  # Increased from 4
            depth=3, 
            max_nodes=60  # Increased from 40
        )

        # Ensure forced seeds are present
        if forced_seeds:
            missing = [fid for fid in forced_seeds if fid not in node_ids]
            for fid in missing:
                node = self.graph_retriever.get_node(fid)
                if node:
                    from src.graph_retriever import _graph_node_to_doc
                    telemetry_docs.insert(0, _graph_node_to_doc(fid, node))
                    node_ids.insert(0, fid)

        # B) Vendor Docs
        vendor_docs: List[Document] = []
        if self.docs_retriever and (_looks_like_docs_question(question) or not _has_entity_anchor(question)):
            vendor_docs = self.docs_retriever.retrieve(question, k=DOCS_RETRIEVER_K)
            
        # C) Runbooks
        runbook_docs: List[Document] = []
        if self.runbooks_retriever and _looks_like_operational_question(question):
            runbook_docs = self.runbooks_retriever.retrieve(question, k=RUNBOOKS_RETRIEVER_K)

        # 3. Build Prompt Context
        context_str = self._render_docs(telemetry_docs, "TELEMETRY CONTEXT")
        context_str += self._render_docs(runbook_docs, "RUNBOOK CONTEXT (Internal Procedures)")
        context_str += self._render_docs(vendor_docs, "VENDOR DOCS")
        
        # 4. Generate Explanation
        graph_explanation = build_graph_explanation(node_ids=node_ids, retriever=self.graph_retriever)
        if focus:
            graph_explanation += "\n\n[focus]\n" + json.dumps(focus, indent=2)

        # 5. Invoke LLM
        llm_prompt_text = (
            ASSISTANT_SYSTEM_PROMPT + "\n\n" + context_str + "\n\nQUESTION:\n" + question
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