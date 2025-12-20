# src/graph_model.py
"""
Phase 1: Graph Model (Lite).
Nodes: Resource, Run, DQ, Metric, Config, Incident.
Edges: Run->Resource, Run->Config, Metric->Resource, Metric->Run, Incident->Resource.
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

def safe_json(val: str) -> Dict[str, Any]:
    if not val:
        return {}
    try:
        return json.loads(val)
    except Exception:
        return {}

def build_reliability_graph(db_path: str, mode: str = "lite", **kwargs) -> Tuple[List[GraphNode], List[GraphEdge]]:
    nodes = []
    edges = []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Resources
    for r in c.execute("SELECT resource_id, name, resource_type, attributes_json FROM resource"):
        nid = f"resource::{r['resource_id']}"
        nodes.append(GraphNode(
            nid, "resource", r['name'], 
            f"Resource: {r['name']} ({r['resource_type']})", 
            safe_json(r['attributes_json'])
        ))

    # 2. Compute Configs
    for cfg in c.execute("SELECT compute_config_id, config_type, config_json FROM compute_config"):
        nid = f"config::{cfg['compute_config_id']}"
        attrs = safe_json(cfg['config_json'])
        config_text = f"Type: {cfg['config_type']}\n"
        for k, v in attrs.items():
            config_text += f"- {k}: {v}\n"
        nodes.append(GraphNode(nid, "config", cfg['compute_config_id'], config_text, attrs))

    # 3. Runs
    for run in c.execute("SELECT run_id, resource_id, compute_config_id, status, started_at, message, attributes_json FROM run ORDER BY started_at DESC LIMIT 50"):
        nid = f"run::{run['run_id']}"
        nodes.append(GraphNode(
            nid, "run", f"Run {run['run_id']}", 
            f"Run Status: {run['status']}\nTime: {run['started_at']}\nMessage: {run['message']}", 
            safe_json(run['attributes_json'])
        ))
        # Edges
        edges.append(GraphEdge(nid, f"resource::{run['resource_id']}", "run_of_resource", {}))
        if run['compute_config_id']:
            edges.append(GraphEdge(nid, f"config::{run['compute_config_id']}", "uses_config", {}))

    # 4. DQ Failures
    for dq in c.execute("SELECT dq_result_id, run_id, status, message FROM dq_result WHERE status='fail' LIMIT 50"):
        nid = f"dq::{dq['dq_result_id']}"
        nodes.append(GraphNode(nid, "dq_result", "DQ Failure", f"DQ Status: {dq['status']} - {dq['message']}", {}))
        if dq['run_id']:
            edges.append(GraphEdge(nid, f"run::{dq['run_id']}", "dq_blames_run", {}))

    # 5. Incidents
    for inc in c.execute("SELECT incident_id, title, severity, summary, attributes_json FROM incident"):
        nid = f"incident::{inc['incident_id']}"
        nodes.append(GraphNode(
            nid, "incident", inc['title'], 
            f"Incident: {inc['title']}\nSeverity: {inc['severity']}\nSummary: {inc['summary']}", 
            safe_json(inc['attributes_json'])
        ))

    # 6. Incident Links
    for link in c.execute("SELECT incident_id, resource_id, relation FROM incident_resource"):
        edges.append(GraphEdge(f"incident::{link['incident_id']}", f"resource::{link['resource_id']}", link['relation'], {}))

    # 7. Metrics (Limit Increased to 500)
    # We fetch enough metrics to cover multiple resources and signals
    metric_sql = """
    SELECT metric_point_id, resource_id, run_id, metric_name, value_number, unit, time 
    FROM metric_point 
    ORDER BY time DESC LIMIT 500
    """
    for m in c.execute(metric_sql):
        nid = f"metric::{m['metric_point_id']}"
        text = f"Metric: {m['metric_name']} = {m['value_number']} {m['unit']} @ {m['time']}"
        nodes.append(GraphNode(nid, "metric", m['metric_name'], text, {}))
        
        # Link to Resource
        if m['resource_id']:
            edges.append(GraphEdge(nid, f"resource::{m['resource_id']}", "metric_of", {}))
        
        # Link to Run
        if m['run_id']:
            edges.append(GraphEdge(nid, f"run::{m['run_id']}", "metric_of_run", {}))

    conn.close()
    return nodes, edges

def build_graph(db_path: str, **kwargs):
    nodes, edges = build_reliability_graph(db_path, **kwargs)
    g = {}
    for n in nodes:
        g[n.id] = {
            "id": n.id, 
            "type": n.type, 
            "title": n.title, 
            "text": n.text, 
            "attrs": n.attrs,
            "neighbors": []
        }
    for e in edges:
        if e.src in g and e.dst in g:
            g[e.src]["neighbors"].append({"id": e.dst, "relation": e.relation_type})
            g[e.dst]["neighbors"].append({"id": e.src, "relation": e.relation_type}) 
    return g