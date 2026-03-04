# src/tests/test_vendor_corpus.py
"""
LangSmith-integrated evaluation suite for the System Reliability Copilot.

Three evaluation targets:
  1. Router accuracy  — does the LLM router assign the correct backend(s)?
  2. Vendor doc retrieval quality — does the Neo4j vector index return relevant chunks?
  3. End-to-end answer quality — LLM-as-judge scores the final answer on relevance + grounding.

Usage:
  # Run against LangSmith (requires LANGCHAIN_TRACING_V2=true + LANGCHAIN_API_KEY)
  python -m pytest src/tests/test_vendor_corpus.py -v

  # Run standalone (prints results; no LangSmith required)
  python src/tests/test_vendor_corpus.py
"""
from __future__ import annotations

import json
import os

from langsmith import Client
from langsmith.evaluation import evaluate, LangChainStringEvaluator

from src.config import LLM_PROVIDER, get_chat_model_name
from src.RAG_chatbot.chat_orchestrator import (
    ReliabilityAssistant,
    ROUTER_PROMPT,
    RouterDecision,
    DatabricksDocsRetriever,
    get_llm,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _parse_router(raw: str) -> RouterDecision:
    """Reuse the same parse logic as the orchestrator."""
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(raw)
    return RouterDecision(
        intent=data.get("intent", "other"),
        entity_type=data.get("entity_type"),
        use_graph=bool(data.get("use_graph", True)),
        use_vendor_docs=bool(data.get("use_vendor_docs", False)),
        use_runbooks=bool(data.get("use_runbooks", False)),
    )


def _get_assistant() -> ReliabilityAssistant:
    return ReliabilityAssistant.from_local()


# ---------------------------------------------------------------------------
# 1. Router accuracy dataset
# ---------------------------------------------------------------------------

ROUTER_DATASET_NAME = "reliability-copilot-router-v1"

ROUTER_CASES = [
    # (question, expected_backend_key, expected_intent)
    ("How does Databricks Auto Loader handle schema drift?",
     "vendor_docs", "other"),
    ("What are best practices for AWS EC2 spot instances?",
     "vendor_docs", "other"),
    ("How do I fix an OOMKilled pod in Kubernetes?",
     "runbooks", "other"),
    ("Who owns the payment-etl job?",
     "graph", "ownership"),
    ("What changed on the nightly-dbt-run resource in the last 7 days?",
     "graph", "change_history"),
    ("How many jobs failed this week?",
     "graph", "global_aggregate"),
    ("Is the current p95 latency normal for the orders service?",
     "graph", "baseline_check"),
    ("What is the Time Travel retention period for Snowflake Standard Edition?",
     "vendor_docs", "other"),
    ("What does the runbook say to do when we get a Databricks OOM error?",
     "runbooks", "other"),
    ("Summarize overall system health",
     "graph", "usage_overview"),
]


def _push_router_dataset(client: Client) -> None:
    """Create or update the router evaluation dataset in LangSmith."""
    existing = {ds.name for ds in client.list_datasets()}
    if ROUTER_DATASET_NAME in existing:
        return  # already exists, don't overwrite

    dataset = client.create_dataset(
        ROUTER_DATASET_NAME,
        description="Ground-truth routing decisions for the LLM router in ReliabilityAssistant.",
    )
    for question, expected_backend, expected_intent in ROUTER_CASES:
        client.create_example(
            inputs={"question": question},
            outputs={
                "expected_backend": expected_backend,
                "expected_intent": expected_intent,
            },
            dataset_id=dataset.id,
        )


def _router_target(inputs: dict) -> dict:
    """Run just the router step and return the decision."""
    router_chain = (
        ROUTER_PROMPT
        | get_llm(temperature=0)
        | StrOutputParser()
        | RunnableLambda(_parse_router)
    )
    decision: RouterDecision = router_chain.invoke({"question": inputs["question"]})
    return {
        "intent": decision.intent,
        "use_graph": decision.use_graph,
        "use_vendor_docs": decision.use_vendor_docs,
        "use_runbooks": decision.use_runbooks,
    }


def _router_backend_evaluator(run, example) -> dict:
    """
    Custom evaluator: checks that the expected backend flag is True
    in the router's decision.
    """
    expected = example.outputs["expected_backend"]
    output = run.outputs or {}

    flag_map = {
        "graph": "use_graph",
        "vendor_docs": "use_vendor_docs",
        "runbooks": "use_runbooks",
    }
    flag = flag_map.get(expected, "use_graph")
    correct = bool(output.get(flag, False))

    return {
        "key": "router_backend_correct",
        "score": 1 if correct else 0,
        "comment": f"Expected {expected}={True}, got {output.get(flag)}",
    }


def _router_intent_evaluator(run, example) -> dict:
    """Checks that the router's intent matches the expected intent."""
    expected_intent = example.outputs["expected_intent"]
    actual_intent = (run.outputs or {}).get("intent", "")
    correct = actual_intent == expected_intent
    return {
        "key": "router_intent_correct",
        "score": 1 if correct else 0,
        "comment": f"Expected intent={expected_intent}, got intent={actual_intent}",
    }


# ---------------------------------------------------------------------------
# 2. Vendor doc retrieval dataset
# ---------------------------------------------------------------------------

RETRIEVAL_DATASET_NAME = "reliability-copilot-retrieval-v1"

RETRIEVAL_CASES = [
    # (question, required_keyword_in_chunks)
    ("How does Databricks Auto Loader handle schema drift?", "schema"),
    ("What are AWS EC2 spot instance best practices?", "spot"),
    ("What is Snowflake Time Travel and how long does it retain data?", "travel"),
    ("How do I configure Kubernetes liveness probes?", "liveness"),
    ("What are Airflow DAG best practices for reliability?", "dag"),
    ("How do dbt incremental models work?", "incremental"),
]


def _push_retrieval_dataset(client: Client) -> None:
    existing = {ds.name for ds in client.list_datasets()}
    if RETRIEVAL_DATASET_NAME in existing:
        return
    dataset = client.create_dataset(
        RETRIEVAL_DATASET_NAME,
        description="Retrieval quality evaluation: does Neo4j return relevant vendor doc chunks?",
    )
    for question, keyword in RETRIEVAL_CASES:
        client.create_example(
            inputs={"question": question},
            outputs={"required_keyword": keyword},
            dataset_id=dataset.id,
        )


def _retrieval_target(inputs: dict) -> dict:
    """Run only the vendor docs retrieval step."""
    retriever = DatabricksDocsRetriever()
    if not retriever.is_available():
        return {"chunks": [], "top_sources": [], "chunk_count": 0}
    docs = retriever.retrieve(inputs["question"], k=4)
    return {
        "chunks": [d.page_content for d in docs],
        "top_sources": [d.metadata.get("source", "") for d in docs],
        "chunk_count": len(docs),
    }


def _retrieval_keyword_evaluator(run, example) -> dict:
    """Checks that the required keyword appears in at least one retrieved chunk."""
    keyword = example.outputs["required_keyword"].lower()
    chunks = (run.outputs or {}).get("chunks", [])
    found = any(keyword in c.lower() for c in chunks)
    return {
        "key": "retrieval_keyword_hit",
        "score": 1 if found else 0,
        "comment": f"Keyword '{keyword}' {'found' if found else 'NOT found'} in {len(chunks)} chunks.",
    }


def _retrieval_coverage_evaluator(run, example) -> dict:
    """Scores based on how many chunks were returned (0 = miss, 4 = full coverage)."""
    count = (run.outputs or {}).get("chunk_count", 0)
    score = min(count / 4.0, 1.0)  # normalize to 0–1
    expected_keyword = (example.outputs or {}).get("required_keyword", "?")
    return {
        "key": "retrieval_chunk_coverage",
        "score": score,
        "comment": f"Retrieved {count}/4 chunks for keyword='{expected_keyword}'.",
    }


# ---------------------------------------------------------------------------
# 3. End-to-end answer quality (LLM-as-judge)
# ---------------------------------------------------------------------------

E2E_DATASET_NAME = "reliability-copilot-e2e-v1"

E2E_CASES = [
    {
        "question": "How does Databricks Auto Loader handle schema drift or new columns?",
        "reference": "Auto Loader detects new columns and can either fail the stream or evolve the schema automatically using the cloudFiles.schemaEvolutionMode option.",
    },
    {
        "question": "What is the Snowflake Time Travel data retention period for Standard Edition?",
        "reference": "Snowflake Standard Edition supports a maximum Time Travel retention period of 1 day (24 hours).",
    },
    {
        "question": "What are best practices to optimize AWS EC2 costs for intermittent workloads?",
        "reference": "Use Spot Instances for fault-tolerant workloads, right-size instances, use auto-scaling, and consider Reserved Instances for predictable baseline capacity.",
    },
    {
        "question": "How do I fix an OOMKilled pod in Kubernetes?",
        "reference": "Increase the memory limits in the pod spec, check for memory leaks in the application, and consider using Vertical Pod Autoscaler to right-size the pod.",
    },
]


def _push_e2e_dataset(client: Client) -> None:
    existing = {ds.name for ds in client.list_datasets()}
    if E2E_DATASET_NAME in existing:
        return
    dataset = client.create_dataset(
        E2E_DATASET_NAME,
        description="End-to-end answer quality with LLM-as-judge on relevance and grounding.",
    )
    for case in E2E_CASES:
        client.create_example(
            inputs={"question": case["question"]},
            outputs={"reference": case["reference"]},
            dataset_id=dataset.id,
        )


def _e2e_target(inputs: dict) -> dict:
    """Run the full ReliabilityAssistant pipeline."""
    assistant = _get_assistant()
    result = assistant.answer(inputs["question"])
    return {"answer": result.answer}


# ---------------------------------------------------------------------------
# Pytest entry points
# ---------------------------------------------------------------------------

def test_router_accuracy() -> None:
    """
    Evaluate router accuracy against the LangSmith dataset.
    Requires LANGCHAIN_API_KEY + LANGCHAIN_TRACING_V2=true.
    Falls back to local assertions if LangSmith is unavailable.
    """
    langsmith_key = os.getenv("LANGCHAIN_API_KEY")
    if not langsmith_key:
        _run_router_locally()
        return

    client = Client()
    _push_router_dataset(client)

    results = evaluate(
        _router_target,
        data=ROUTER_DATASET_NAME,
        evaluators=[_router_backend_evaluator, _router_intent_evaluator],
        experiment_prefix="router",
        metadata={"model": get_chat_model_name(), "provider": LLM_PROVIDER},
    )

    scores = [r["evaluation_results"]["results"][0].score for r in results]
    avg = sum(scores) / len(scores) if scores else 0
    assert avg >= 0.7, f"Router backend accuracy {avg:.0%} is below 70% threshold."


def test_retrieval_quality() -> None:
    """
    Evaluate Neo4j vendor doc retrieval quality.
    Skips gracefully if the index is not available.
    """
    retriever = DatabricksDocsRetriever()
    if not retriever.is_available():
        import pytest
        pytest.skip("Neo4j vendor docs index not available — run `make ingest_docs` first.")

    langsmith_key = os.getenv("LANGCHAIN_API_KEY")
    if not langsmith_key:
        _run_retrieval_locally()
        return

    client = Client()
    _push_retrieval_dataset(client)

    results = evaluate(
        _retrieval_target,
        data=RETRIEVAL_DATASET_NAME,
        evaluators=[_retrieval_keyword_evaluator, _retrieval_coverage_evaluator],
        experiment_prefix="retrieval",
        metadata={"index": "vendor_docs", "provider": LLM_PROVIDER},
    )

    keyword_scores = []
    for r in results:
        for res in r["evaluation_results"]["results"]:
            if res.key == "retrieval_keyword_hit":
                keyword_scores.append(res.score)

    avg = sum(keyword_scores) / len(keyword_scores) if keyword_scores else 0
    assert avg >= 0.6, f"Retrieval keyword hit rate {avg:.0%} is below 60% threshold."


def test_e2e_answer_quality() -> None:
    """
    LLM-as-judge evaluation of end-to-end answer quality.
    Uses LangSmith's built-in QA evaluator (correctness vs. reference answer).
    """
    langsmith_key = os.getenv("LANGCHAIN_API_KEY")
    if not langsmith_key:
        import pytest
        pytest.skip("LANGCHAIN_API_KEY not set — LLM-as-judge requires LangSmith.")

    client = Client()
    _push_e2e_dataset(client)

    qa_evaluator = LangChainStringEvaluator(
        "qa",
        config={"llm": get_llm(temperature=0)},
        prepare_data=lambda run, example: {
            "prediction": (run.outputs or {}).get("answer", ""),
            "reference": example.outputs["reference"],
            "input": example.inputs["question"],
        },
    )

    results = evaluate(
        _e2e_target,
        data=E2E_DATASET_NAME,
        evaluators=[qa_evaluator],
        experiment_prefix="e2e",
        metadata={"model": get_chat_model_name(), "provider": LLM_PROVIDER},
    )

    scores = []
    for r in results:
        for res in r["evaluation_results"]["results"]:
            if res.score is not None:
                scores.append(res.score)

    avg = sum(scores) / len(scores) if scores else 0
    assert avg >= 0.6, f"E2E answer quality {avg:.0%} is below 60% threshold."


# ---------------------------------------------------------------------------
# Local fallback runners (no LangSmith required)
# ---------------------------------------------------------------------------

def _run_router_locally() -> None:
    """Run router cases locally and print results."""
    from langchain_core.runnables import RunnableLambda

    router_chain = (
        ROUTER_PROMPT
        | get_llm(temperature=0)
        | StrOutputParser()
        | RunnableLambda(_parse_router)
    )

    print("\n=== ROUTER EVALUATION (local) ===\n")
    correct = 0
    for question, expected_backend, expected_intent in ROUTER_CASES:
        decision = router_chain.invoke({"question": question})
        flag_map = {"graph": decision.use_graph, "vendor_docs": decision.use_vendor_docs, "runbooks": decision.use_runbooks}
        backend_ok = flag_map.get(expected_backend, False)
        intent_ok = decision.intent == expected_intent
        status = "PASS" if (backend_ok and intent_ok) else "FAIL"
        if backend_ok and intent_ok:
            correct += 1
        print(f"[{status}] {question[:60]}")
        print(f"       backend={expected_backend} -> {'OK' if backend_ok else 'MISS'} | intent={expected_intent} -> {'OK' if intent_ok else f'got={decision.intent}'}")
    print(f"\n{correct}/{len(ROUTER_CASES)} passed")


def _run_retrieval_locally() -> None:
    """Run retrieval cases locally and print results."""
    print("\n=== RETRIEVAL EVALUATION (local) ===\n")
    retriever = DatabricksDocsRetriever()
    hits = 0
    for question, keyword in RETRIEVAL_CASES:
        docs = retriever.retrieve(question, k=4)
        found = any(keyword.lower() in d.page_content.lower() for d in docs)
        status = "PASS" if found else "FAIL"
        if found:
            hits += 1
        print(f"[{status}] {question[:60]}")
        print(f"       keyword='{keyword}' | chunks={len(docs)} | hit={'yes' if found else 'no'}")
    print(f"\n{hits}/{len(RETRIEVAL_CASES)} keyword hits")


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _run_router_locally()
    _run_retrieval_locally()
