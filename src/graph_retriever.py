# src/graph_retriever.py
"""
Graph retriever for the Reliability Copilot (Phase 1 Compatible).
Updates:
- Serializes JSON attributes into LLM-readable text.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Try importing types, but define fallbacks if Phase 1 model is stripped down
try:
    from .graph_model import Graph, NodeId, build_graph
except ImportError:
    NodeId = str
    Graph = Dict[NodeId, Dict[str, Any]]
    from .graph_model import build_graph

# ----------------------------
# Public result structures
# ----------------------------

@dataclass
class GraphHit:
    node_id: NodeId
    score: float
    title: str
    node_type: str
    snippet: str
    attrs: Dict[str, Any]

@dataclass
class Subgraph:
    nodes: Dict[NodeId, Dict[str, Any]]
    edges: List[Tuple[NodeId, NodeId, str]]

# ----------------------------
# Retriever
# ----------------------------

class GraphRAGRetriever:
    def __init__(
        self,
        *,
        db_path: Optional[str] = None,
        graph: Optional[Graph] = None,
        mode: str = "lite",
        days_back: Optional[int] = None,
        max_runs: Optional[int] = None,
        include_otel: bool = True,
    ):
        if graph is None:
            if not db_path:
                raise ValueError("Provide either graph=... or db_path=...")
            graph = build_graph(
                db_path,
                mode=mode,
                days_back=days_back,
                max_runs=max_runs,
                include_otel=include_otel,
            )
        self.graph: Graph = graph

        # Build inverted index for search
        self._search_rows: List[Tuple[NodeId, str]] = []
        for nid, n in self.graph.items():
            title = (n.get("title") or "").lower()
            text = (n.get("text") or "").lower()
            
            # Index attributes too so we can search by "critical" or "p0"
            attrs = n.get("attrs") or {}
            attr_text = " ".join([f"{k} {v}" for k, v in attrs.items()]).lower()
            
            blob = f"{title}\n{text}\n{attr_text}"
            self._search_rows.append((nid, blob))

        self._adj = None

    @classmethod
    def from_local_index(
        cls,
        db_path: str = "data/reliability.db",
        mode: str = "demo",
        days_back: Optional[int] = None
    ) -> "GraphRAGRetriever":
        if not os.path.exists(db_path) and os.path.exists(f"../{db_path}"):
            db_path = f"../{db_path}"
        return cls(db_path=db_path, mode=mode, days_back=days_back)
    
    # ----------------------------
    # Basic graph access
    # ----------------------------

    def get_node(self, node_id: NodeId) -> Dict[str, Any]:
        return self.graph.get(node_id, {})

    def neighbors(self, node_id: NodeId) -> List[Dict[str, Any]]:
        node = self.graph.get(node_id)
        if not node:
            return []
        return node.get("neighbors", []) or []

    # ----------------------------
    # Search
    # ----------------------------

    def _tokenize(self, q: str) -> List[str]:
        q = (q or "").strip().lower()
        return [t for t in re.split(r"[^a-z0-9_.:-]+", q) if t]

    def search(self, query: str, *, limit: int = 10, node_types: Optional[Set[str]] = None) -> List[GraphHit]:
        toks = self._tokenize(query)
        if not toks:
            return []

        hits: List[GraphHit] = []
        for nid, blob in self._search_rows:
            n = self.graph[nid]
            if node_types and (n.get("type") not in node_types):
                continue

            matched = 0
            for t in toks:
                if t in blob:
                    matched += 1
            if matched == 0:
                continue

            score = matched / max(1, len(toks))
            snippet = (n.get("text") or "")[:240]
            hits.append(
                GraphHit(
                    node_id=nid,
                    score=score,
                    title=n.get("title") or nid,
                    node_type=n.get("type") or "unknown",
                    snippet=snippet,
                    attrs=n.get("attrs") or {},
                )
            )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    # ----------------------------
    # Subgraph expansion
    # ----------------------------

    def expand(
        self,
        seed_node_ids: Iterable[NodeId],
        *,
        depth: int = 2,
        max_nodes: int = 80,
        allowed_relation_types: Optional[Set[str]] = None,
    ) -> Subgraph:
        seeds = [nid for nid in seed_node_ids if nid in self.graph]
        if not seeds:
            return Subgraph(nodes={}, edges=[])

        visited: Set[NodeId] = set(seeds)
        frontier: List[Tuple[NodeId, int]] = [(nid, 0) for nid in seeds]
        edges_out: List[Tuple[NodeId, NodeId, str]] = []

        while frontier and len(visited) < max_nodes:
            nid, d = frontier.pop(0)
            if d >= depth:
                continue

            for nb in self.neighbors(nid):
                other = nb["id"]
                et = nb.get("relation") or nb.get("relation_type") or "related"
                
                if allowed_relation_types and et not in allowed_relation_types:
                    continue
                if other not in self.graph:
                    continue
                
                edges_out.append((nid, other, et))

                if other not in visited:
                    visited.add(other)
                    frontier.append((other, d + 1))

        nodes_out = {nid: self.graph[nid] for nid in visited if nid in self.graph}
        unique_edges = list(set((a, b, c) for a, b, c in edges_out))

        return Subgraph(nodes=nodes_out, edges=unique_edges)

    def retrieve_subgraph_for_query(
        self,
        query: str,
        *,
        seed_limit: int = 5,
        depth: int = 2,
        max_nodes: int = 80,
    ) -> Tuple[List[GraphHit], Subgraph]:
        hits = self.search(query, limit=seed_limit)
        seed_ids = [h.node_id for h in hits]
        sg = self.expand(seed_ids, depth=depth, max_nodes=max_nodes)
        return hits, sg


# ---------------------------------------------------------------------------
# Backwards-compat helpers
# ---------------------------------------------------------------------------

try:
    from langchain.schema import Document
except ImportError:
    @dataclass
    class Document:
        page_content: str
        metadata: Dict[str, Any]

@dataclass
class _CompatNode:
    type: str
    properties: Dict[str, Any]

@dataclass
class _CompatAdj:
    nodes: Dict[str, _CompatNode]
    neighbors: Dict[str, Set[str]]

def _build_compat_adj(graph: Graph) -> _CompatAdj:
    nodes: Dict[str, _CompatNode] = {}
    neighbors: Dict[str, Set[str]] = {}

    for nid, n in graph.items():
        ntype = str(n.get("type") or "unknown")
        props = dict(n.get("attrs") or {})
        if "title" not in props:
            props["title"] = n.get("title")
        nodes[nid] = _CompatNode(type=ntype, properties=props)

        if nid not in neighbors:
            neighbors[nid] = set()
        
        nb_list = n.get("neighbors", [])
        for nb in nb_list:
            other_id = nb["id"]
            neighbors[nid].add(other_id)
            if other_id not in neighbors:
                neighbors[other_id] = set()
            neighbors[other_id].add(nid)

    return _CompatAdj(nodes=nodes, neighbors=neighbors)

def _graph_node_to_doc(nid: str, n: Dict[str, Any]) -> Document:
    title = n.get("title") or nid
    ntype = n.get("type") or "unknown"
    attrs = n.get("attrs") or {}
    text = n.get("text") or ""

    # === CRITICAL FIX: Serialize Attributes into Text ===
    # This ensures the LLM sees the JSON config (e.g. "retention_days: 1")
    if attrs:
        attr_lines = [f"  - {k}: {v}" for k, v in attrs.items()]
        text += "\n[Attributes]:\n" + "\n".join(attr_lines)
    # ====================================================

    header = f"[{ntype}] {title} (node_id={nid})"
    return Document(
        page_content=header + "\n" + text,
        metadata={"source": "graph", "node_id": nid, "node_type": ntype}
    )

def _adj_property(self) -> _CompatAdj:
    if getattr(self, "_adj", None) is None:
        self._adj = _build_compat_adj(self.graph)
    return self._adj

def _get_subgraph_for_query(self, query: str, **kwargs):
    hits, sg = self.retrieve_subgraph_for_query(query, **kwargs)
    docs = [_graph_node_to_doc(nid, n) for nid, n in sg.nodes.items()]
    return docs, list(sg.nodes.keys())

GraphRAGRetriever.adj = property(_adj_property) # type: ignore
GraphRAGRetriever.get_subgraph_for_query = _get_subgraph_for_query # type: ignore