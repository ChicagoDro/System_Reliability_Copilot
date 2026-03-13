# src/RAG_build/ingest_embed_index.py
"""
Embed Reliability Copilot RAG docs into Neo4j (vector + graph).

Ingestion entrypoint for the Reliability Copilot schema.

Writes two things to Neo4j:
  1. Vector index  — each RagDoc becomes a labeled node with an embedding,
                     queryable via Neo4jVector similarity search.
  2. Graph topology — Platform/Environment/Resource nodes and their
                     relationships (BELONGS_TO, IN_ENV, RELATES_TO, etc.)
                     so graph-traversal queries can follow lineage edges,
                     find incidents per environment, etc.

Examples:
  python -m src.RAG_build.ingest_embed_index --db-path data/reliability.db
  python -m src.RAG_build.ingest_embed_index --db-path data/reliability.db --skip-graph
  python -m src.RAG_build.ingest_embed_index --db-path data/reliability.db --skip-vectors
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import argparse
import os
import sqlite3
from typing import List, Optional

from langchain_core.documents import Document
from langchain_community.vectorstores import Neo4jVector

from .ingest_reliability_domain import RagDoc, build_reliability_rag_docs
from src.config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    NEO4J_RELIABILITY_INDEX,
    get_embed_model_name,
)


# ----------------------------
# Embeddings factory
# ----------------------------

def _get_embeddings(provider: str, model: Optional[str] = None):
    provider = (provider or "").strip().lower()

    if provider in ("openai", "oai"):
        try:
            from langchain_openai import OpenAIEmbeddings
        except Exception as e:
            raise RuntimeError(
                "OpenAI embeddings selected but langchain_openai is not installed."
            ) from e
        return OpenAIEmbeddings(model=model or get_embed_model_name())

    if provider in ("gemini", "google"):
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
        except Exception as e:
            raise RuntimeError(
                "Gemini embeddings selected but langchain_google_genai is not installed."
            ) from e
        return GoogleGenerativeAIEmbeddings(model=model or get_embed_model_name())

    if provider in ("huggingface", "sentence_transformers", "sbert"):
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
        except Exception as e:
            raise RuntimeError(
                "HuggingFace embeddings selected but dependencies are missing."
            ) from e
        return HuggingFaceEmbeddings(
            model_name=model
            or os.getenv("HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )

    raise ValueError(f"Unknown provider: {provider}. Use openai, gemini, or huggingface.")


def _to_langchain_docs(rag_docs: List[RagDoc]) -> List[Document]:
    out: List[Document] = []
    for d in rag_docs:
        extra_meta = getattr(d, "metadata", None) or {}
        out.append(
            Document(
                page_content=d.text,
                metadata={"doc_id": d.doc_id, **extra_meta},
            )
        )
    return out


# ----------------------------
# Graph ingestion
# ----------------------------

def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    return any(r["name"] == col for r in rows)


def ingest_graph(db_path: str) -> None:
    """
    Reads the SQLite schema and writes a graph topology into Neo4j:

    Nodes:
      (:Platform   {platform_id, platform_type, display_name})
      (:Environment {env_id, env_type, region})
      (:Resource    {resource_id, name, resource_type, namespace, owner, external_id, platform_id, env_id})
      (:Incident    {incident_id, title, severity, status, opened_at, closed_at})
      (:Run         {run_id, run_type, status, started_at, ended_at, resource_id})

    Relationships:
      (:Resource)-[:BELONGS_TO]->(:Platform)
      (:Resource)-[:IN_ENV]->(:Environment)
      (:Resource)-[:RELATES_TO {relation_type, edge_id}]->(:Resource)   (lineage)
      (:Incident)-[:OCCURRED_IN]->(:Environment)
      (:Run)-[:EXECUTED_ON]->(:Resource)
    """
    from neo4j import GraphDatabase  # type: ignore

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    with _get_conn(db_path) as conn, driver.session(database=NEO4J_DATABASE) as session:

        # ---- Full-text index (covers all ReliabilityNode-labeled nodes) ----
        session.run("""
            CREATE FULLTEXT INDEX reliabilityFullText IF NOT EXISTS
            FOR (n:ReliabilityNode) ON EACH [n.title, n.text]
        """)

        # ---- Platforms ----
        platforms = conn.execute(
            "SELECT platform_id, platform_type, display_name FROM platform"
        ).fetchall()
        for p in platforms:
            session.run(
                """
                MERGE (n:Platform {platform_id: $platform_id})
                SET n:ReliabilityNode,
                    n.node_id       = $node_id,
                    n.node_type     = 'platform',
                    n.title         = $display_name,
                    n.text          = $text,
                    n.platform_type = $platform_type,
                    n.display_name  = $display_name
                """,
                platform_id=p["platform_id"],
                node_id=f"platform::{p['platform_id']}",
                platform_type=p["platform_type"],
                display_name=p["display_name"],
                text=(
                    f"Platform: {p['display_name']}\n"
                    f"- Type: {p['platform_type']}\n"
                    f"- ID: {p['platform_id']}"
                ),
            )
        print(f"  Graph: merged {len(platforms)} Platform nodes")

        # ---- Environments ----
        envs = conn.execute(
            "SELECT env_id, env_type, region FROM environment"
        ).fetchall()
        for e in envs:
            session.run(
                """
                MERGE (n:Environment {env_id: $env_id})
                SET n:ReliabilityNode,
                    n.node_id   = $node_id,
                    n.node_type = 'environment',
                    n.title     = $env_id,
                    n.text      = $text,
                    n.env_type  = $env_type,
                    n.region    = $region
                """,
                env_id=e["env_id"],
                node_id=f"environment::{e['env_id']}",
                env_type=e["env_type"],
                region=e["region"],
                text=(
                    f"Environment: {e['env_id']}\n"
                    f"- Type: {e['env_type']}\n"
                    f"- Region: {e['region']}"
                ),
            )
        print(f"  Graph: merged {len(envs)} Environment nodes")

        # ---- Resources + relationships to Platform/Environment ----
        has_is_active = _has_column(conn, "resource", "is_active")
        is_active_expr = "r.is_active" if has_is_active else "1 AS is_active"
        resources = conn.execute(f"""
            SELECT r.resource_id, r.platform_id, r.env_id, r.resource_type,
                   r.external_id, r.name, r.namespace, r.owner, {is_active_expr}
            FROM resource r
        """).fetchall()
        for r in resources:
            is_active = bool(r["is_active"]) if r["is_active"] is not None else True
            session.run(
                """
                MERGE (n:Resource {resource_id: $resource_id})
                SET n:ReliabilityNode,
                    n.node_id       = $node_id,
                    n.node_type     = 'resource',
                    n.title         = $name,
                    n.text          = $text,
                    n.name          = $name,
                    n.resource_type = $resource_type,
                    n.namespace     = $namespace,
                    n.owner         = $owner,
                    n.external_id   = $external_id,
                    n.platform_id   = $platform_id,
                    n.env_id        = $env_id,
                    n.is_active     = $is_active
                WITH n
                MATCH (p:Platform {platform_id: $platform_id})
                MERGE (n)-[:BELONGS_TO]->(p)
                WITH n
                MATCH (e:Environment {env_id: $env_id})
                MERGE (n)-[:IN_ENV]->(e)
                """,
                resource_id=r["resource_id"],
                node_id=f"resource::{r['resource_id']}",
                name=r["name"],
                resource_type=r["resource_type"],
                namespace=r["namespace"],
                owner=r["owner"],
                external_id=r["external_id"],
                platform_id=r["platform_id"],
                env_id=r["env_id"],
                is_active=is_active,
                text=(
                    f"Resource: {r['name']} ({r['resource_type']})\n"
                    f"- Owner: {r['owner']}\n"
                    f"- Platform: {r['platform_id']}\n"
                    f"- Environment: {r['env_id']}\n"
                    f"- Namespace: {r['namespace']}\n"
                    f"- Active: {is_active}"
                ),
            )
        print(f"  Graph: merged {len(resources)} Resource nodes")

        # ---- Lineage edges ----
        try:
            edges = conn.execute(
                "SELECT edge_id, src_resource_id, dst_resource_id, relation_type FROM lineage_edge"
            ).fetchall()
            for e in edges:
                session.run(
                    """
                    MATCH (src:Resource {resource_id: $src})
                    MATCH (dst:Resource {resource_id: $dst})
                    MERGE (src)-[r:RELATES_TO {edge_id: $edge_id}]->(dst)
                    SET r.relation_type = $relation_type
                    """,
                    src=e["src_resource_id"],
                    dst=e["dst_resource_id"],
                    edge_id=e["edge_id"],
                    relation_type=e["relation_type"],
                )
            print(f"  Graph: merged {len(edges)} RELATES_TO lineage edges")
        except sqlite3.OperationalError:
            print("  Graph: lineage_edge table not found, skipping")

        # ---- Incidents ----
        try:
            incidents = conn.execute(
                "SELECT incident_id, env_id, title, severity, status, opened_at, closed_at FROM incident"
            ).fetchall()
            for i in incidents:
                session.run(
                    """
                    MERGE (n:Incident {incident_id: $incident_id})
                    SET n:ReliabilityNode,
                        n.node_id   = $node_id,
                        n.node_type = 'incident',
                        n.title     = $title,
                        n.text      = $text,
                        n.severity  = $severity,
                        n.status    = $status,
                        n.opened_at = $opened_at,
                        n.closed_at = $closed_at,
                        n.env_id    = $env_id
                    WITH n
                    MATCH (e:Environment {env_id: $env_id})
                    MERGE (n)-[:OCCURRED_IN]->(e)
                    """,
                    incident_id=i["incident_id"],
                    node_id=f"incident::{i['incident_id']}",
                    env_id=i["env_id"],
                    title=i["title"],
                    severity=i["severity"],
                    status=i["status"],
                    opened_at=i["opened_at"],
                    closed_at=i["closed_at"],
                    text=(
                        f"Incident: {i['title']}\n"
                        f"- Severity: {i['severity']}\n"
                        f"- Status: {i['status']}\n"
                        f"- Environment: {i['env_id']}\n"
                        f"- Opened: {i['opened_at']}\n"
                        f"- Closed: {i['closed_at']}"
                    ),
                )
            print(f"  Graph: merged {len(incidents)} Incident nodes")
        except sqlite3.OperationalError:
            print("  Graph: incident table not found, skipping")

        # ---- Runs ----
        try:
            runs = conn.execute(
                "SELECT run_id, resource_id, run_type, status, started_at, ended_at FROM run"
            ).fetchall()
            for r in runs:
                session.run(
                    """
                    MERGE (n:Run {run_id: $run_id})
                    SET n:ReliabilityNode,
                        n.node_id     = $node_id,
                        n.node_type   = 'run',
                        n.title       = $title,
                        n.text        = $text,
                        n.run_type    = $run_type,
                        n.status      = $status,
                        n.started_at  = $started_at,
                        n.ended_at    = $ended_at,
                        n.resource_id = $resource_id
                    WITH n
                    MATCH (res:Resource {resource_id: $resource_id})
                    MERGE (n)-[:EXECUTED_ON]->(res)
                    """,
                    run_id=r["run_id"],
                    node_id=f"run::{r['run_id']}",
                    resource_id=r["resource_id"],
                    run_type=r["run_type"],
                    status=r["status"],
                    started_at=r["started_at"],
                    ended_at=r["ended_at"],
                    title=f"Run {r['run_id']}",
                    text=(
                        f"Run: {r['run_id']}\n"
                        f"- Type: {r['run_type']}\n"
                        f"- Status: {r['status']}\n"
                        f"- Resource: {r['resource_id']}\n"
                        f"- Started: {r['started_at']}\n"
                        f"- Ended: {r['ended_at']}"
                    ),
                )
            print(f"  Graph: merged {len(runs)} Run nodes")
        except sqlite3.OperationalError:
            print("  Graph: run table not found, skipping")

    driver.close()


# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Ingest Reliability Copilot data into Neo4j (vector index + graph topology)."
    )
    ap.add_argument("--db-path", required=True, help="Path to reliability SQLite DB.")
    ap.add_argument(
        "--provider",
        default=os.getenv("EMBEDDINGS_PROVIDER") or os.getenv("LLM_PROVIDER", "openai"),
        help="Embeddings provider: openai|gemini|huggingface",
    )
    ap.add_argument("--embed-model", default=None)
    ap.add_argument("--days-back", type=int, default=None)
    ap.add_argument("--index-name", default=NEO4J_RELIABILITY_INDEX)
    ap.add_argument("--skip-vectors", action="store_true", help="Skip vector index ingestion.")
    ap.add_argument("--skip-graph",   action="store_true", help="Skip graph topology ingestion.")
    args = ap.parse_args()

    if not args.skip_vectors:
        print("Building RAG documents from SQLite...")
        rag_docs = build_reliability_rag_docs(
            db_path=args.db_path,
            days_back=args.days_back,
        )
        lc_docs = _to_langchain_docs(rag_docs)
        embeddings = _get_embeddings(args.provider, args.embed_model)

        print(f"Embedding {len(lc_docs)} docs into Neo4j vector index '{args.index_name}'...")
        Neo4jVector.from_documents(
            lc_docs,
            embeddings,
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            database=NEO4J_DATABASE,
            index_name=args.index_name,
            node_label="ReliabilityDoc",
            text_node_property="text",
            embedding_node_property="embedding",
            pre_delete_collection=True,
        )
        print(f"  Vector index '{args.index_name}' written ({len(lc_docs)} docs, provider={args.provider})")

    if not args.skip_graph:
        print("Ingesting graph topology into Neo4j...")
        ingest_graph(args.db_path)
        print("  Graph topology ingestion complete.")

    print("Done.")


if __name__ == "__main__":
    main()
