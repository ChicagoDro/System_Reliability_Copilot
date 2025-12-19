# src/reliability_copilot/graph_model.py
"""
Phase 1: Graph Model (Lite).
Nodes: Resource, Run, DQ, OTel.
Edges: Run->Resource, DQ->Run, OTel->Run.
SKIPPED: Lineage, Compute Config.
"""

from __future__ import annotations
import json
import sqlite3
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

@dataclass
class GraphNode:
    id: str
    type: str
    title: str
    text: str
    attrs: Dict[str, Any]

@dataclass
class GraphEdge:
    src: str
    dst: str
    relation_type: str
    attrs: Dict[str, Any]

def build_reliability_graph(db_path: str, mode: str = "lite", **kwargs) -> Tuple[List[GraphNode], List[GraphEdge]]:
    # FORCE LITE MODE FOR PHASE 1
    nodes = []
    edges = []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Resources
    for r in c.execute("SELECT resource_id, name, resource_type FROM resource"):
        nid = f"resource::{r['resource_id']}"
        nodes.append(GraphNode(nid, "resource", r['name'], f"Resource: {r['name']} ({r['resource_type']})", {}))

    # 2. Runs (Recent 50 only)
    for run in c.execute("SELECT run_id, resource_id, status, started_at, message FROM run ORDER BY started_at DESC LIMIT 50"):
        nid = f"run::{run['run_id']}"
        nodes.append(GraphNode(nid, "run", f"Run {run['run_id']}", f"Run Status: {run['status']} Msg: {run['message']}", {}))
        # Edge: Run -> Resource
        edges.append(GraphEdge(nid, f"resource::{run['resource_id']}", "run_of_resource", {}))

    # 3. DQ Failures
    for dq in c.execute("SELECT dq_result_id, run_id, status FROM dq_result WHERE status='fail' LIMIT 50"):
        nid = f"dq::{dq['dq_result_id']}"
        nodes.append(GraphNode(nid, "dq_result", "DQ Failure", f"DQ Status: {dq['status']}", {}))
        if dq['run_id']:
            # Edge: DQ -> Run
            edges.append(GraphEdge(nid, f"run::{dq['run_id']}", "dq_blames_run", {}))

    conn.close()
    return nodes, edges

def build_graph(db_path: str, **kwargs):
    nodes, edges = build_reliability_graph(db_path, **kwargs)
    # Simple dict conversion for retriever
    g = {}
    for n in nodes:
        g[n.id] = {"id": n.id, "type": n.type, "title": n.title, "text": n.text, "neighbors": []}
    for e in edges:
        if e.src in g and e.dst in g:
            g[e.src]["neighbors"].append({"id": e.dst, "relation": e.relation_type})
            g[e.dst]["neighbors"].append({"id": e.src, "relation": e.relation_type}) # Bi-directional for nav
    return g