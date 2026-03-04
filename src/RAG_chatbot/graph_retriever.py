# src/graph_retriever.py
"""
Neo4j-backed graph retriever for the Reliability Copilot.
Replaces the previous in-memory / SQLite implementation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from langchain_core.documents import Document

from src.config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE

# ---------------------------------------------------------------------------
# Public result types
# ---------------------------------------------------------------------------

@dataclass
class GraphHit:
    node_id: str
    score: float
    title: str
    node_type: str
    snippet: str
    attrs: Dict[str, Any]

@dataclass
class Subgraph:
    nodes: Dict[str, Dict[str, Any]]
    edges: List[Tuple[str, str, str]]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _escape_lucene(query: str) -> str:
    """Escape Lucene special characters and format as OR query."""
    special = r'[+\-&|!(){}[\]^"~*?:\\/]'
    tokens = [t for t in re.split(r"\s+", query.strip()) if t]
    escaped = [re.sub(special, r"\\\g<0>", t) for t in tokens]
    return " OR ".join(escaped) if escaped else "*"

def _node_to_dict(record_node) -> Dict[str, Any]:
    """Convert a neo4j Node object to a plain dict."""
    return dict(record_node)

def _graph_node_to_doc(nid: str, n: Dict[str, Any]) -> Document:
    """Convert a Neo4j node dict to a LangChain Document."""
    title  = n.get("title") or nid
    ntype  = n.get("node_type") or n.get("type") or "unknown"
    text   = n.get("text") or ""

    # attrs stored as JSON string in Neo4j
    attrs: Dict[str, Any] = {}
    raw_attrs = n.get("attrs_json") or n.get("attrs") or "{}"
    if isinstance(raw_attrs, str):
        try:
            attrs = json.loads(raw_attrs)
        except Exception:
            attrs = {}
    elif isinstance(raw_attrs, dict):
        attrs = raw_attrs

    if attrs:
        attr_lines = [f"  - {k}: {v}" for k, v in attrs.items()]
        text += "\n[Attributes]:\n" + "\n".join(attr_lines)

    header = f"[{ntype}] {title} (node_id={nid})"
    return Document(
        page_content=header + "\n" + text,
        metadata={"source": "graph", "node_id": nid, "node_type": ntype},
    )

# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class GraphRAGRetriever:
    """
    Queries Neo4j for graph-based retrieval.
    All search and traversal logic is expressed as Cypher.
    """

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        from neo4j import GraphDatabase
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create the full-text index if it doesn't already exist."""
        with self.driver.session(database=self.database) as s:
            s.run("""
                CREATE FULLTEXT INDEX reliabilityFullText IF NOT EXISTS
                FOR (n:ReliabilityNode) ON EACH [n.title, n.text]
            """)

    @classmethod
    def from_local_index(cls, *args, **kwargs) -> "GraphRAGRetriever":
        """Connect to Neo4j using env-configured credentials."""
        return cls(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE)

    # ------------------------------------------------------------------
    # Node access
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Dict[str, Any]:
        with self.driver.session(database=self.database) as s:
            result = s.run(
                "MATCH (n:ReliabilityNode {node_id: $nid}) RETURN n LIMIT 1",
                nid=node_id,
            )
            record = result.single()
            return _node_to_dict(record["n"]) if record else {}

    def neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        with self.driver.session(database=self.database) as s:
            result = s.run(
                """
                MATCH (n:ReliabilityNode {node_id: $nid})-[r]-(m:ReliabilityNode)
                RETURN m.node_id AS id, type(r) AS relation
                LIMIT 50
                """,
                nid=node_id,
            )
            return [{"id": r["id"], "relation": r["relation"]} for r in result]

    def count_nodes_by_type(self, node_type: str) -> int:
        with self.driver.session(database=self.database) as s:
            result = s.run(
                "MATCH (n:ReliabilityNode {node_type: $nt}) RETURN count(n) AS cnt",
                nt=node_type.lower(),
            )
            record = result.single()
            return record["cnt"] if record else 0

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        node_types: Optional[Set[str]] = None,
    ) -> List[GraphHit]:
        lucene_q = _escape_lucene(query)
        with self.driver.session(database=self.database) as s:
            if node_types:
                result = s.run(
                    """
                    CALL db.index.fulltext.queryNodes('reliabilityFullText', $q)
                    YIELD node, score
                    WHERE node.node_type IN $types
                    RETURN node, score
                    LIMIT $limit
                    """,
                    q=lucene_q,
                    types=list(node_types),
                    limit=limit,
                )
            else:
                result = s.run(
                    """
                    CALL db.index.fulltext.queryNodes('reliabilityFullText', $q)
                    YIELD node, score
                    RETURN node, score
                    LIMIT $limit
                    """,
                    q=lucene_q,
                    limit=limit,
                )

            hits: List[GraphHit] = []
            for rec in result:
                node = _node_to_dict(rec["node"])
                hits.append(GraphHit(
                    node_id=node.get("node_id", ""),
                    score=rec["score"],
                    title=node.get("title", ""),
                    node_type=node.get("node_type", "unknown"),
                    snippet=node.get("text", "")[:240],
                    attrs=json.loads(node.get("attrs_json") or "{}"),
                ))
            return hits

    # ------------------------------------------------------------------
    # Subgraph expansion
    # ------------------------------------------------------------------

    def get_subgraph_for_query(
        self,
        query: str,
        *,
        seed_limit: int = 5,
        depth: int = 3,
        max_nodes: int = 60,
        seed_node_types: Optional[Set[str]] = None,
    ) -> Tuple[List[Document], List[str]]:
        """
        Full-text search for seeds, then BFS-expand via Cypher path traversal.
        Returns (docs, node_ids) matching the interface expected by chat_orchestrator.

        seed_node_types: when provided, the full-text seed search is filtered to
        those node types (e.g. {"owner"} for ownership queries). The BFS expansion
        from those seeds still traverses all node types so related context is included.
        """
        seed_hits = self.search(query, limit=seed_limit, node_types=seed_node_types)
        if not seed_hits:
            return [], []

        seed_ids = [h.node_id for h in seed_hits]

        with self.driver.session(database=self.database) as s:
            result = s.run(
                f"""
                MATCH (seed:ReliabilityNode)
                WHERE seed.node_id IN $seed_ids
                MATCH path = (seed)-[*0..{depth}]-(neighbor:ReliabilityNode)
                WITH DISTINCT neighbor
                LIMIT $max_nodes
                RETURN neighbor
                """,
                seed_ids=seed_ids,
                max_nodes=max_nodes,
            )

            docs: List[Document] = []
            node_ids: List[str] = []
            for rec in result:
                node = _node_to_dict(rec["neighbor"])
                nid = node.get("node_id", "")
                node_ids.append(nid)
                docs.append(_graph_node_to_doc(nid, node))

        return docs, node_ids
