# src/graph_model.py
"""
Enhanced Graph Model with Ownership, Change History, and Baselines.
Nodes: Resource, Run, DQ, Metric, Config, Incident, Owner, Change, Baseline, SLA, Cost.
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

    # 1. Resources (Enhanced with SLA/Cost metadata)
    for r in c.execute("SELECT resource_id, name, resource_type, owner, attributes_json FROM resource"):
        nid = f"resource::{r['resource_id']}"
        attrs = safe_json(r['attributes_json'])
        
        # Build rich text summary
        text = f"Resource: {r['name']} ({r['resource_type']})\nOwner: {r['owner']}"
        if 'priority' in attrs:
            text += f"\nPriority: {attrs['priority']}"
        if 'sla_runtime_mins' in attrs:
            text += f"\nSLA: {attrs['sla_runtime_mins']} minutes"
        
        nodes.append(GraphNode(nid, "resource", r['name'], text, attrs))

    # 2. Compute Configs
    for cfg in c.execute("SELECT compute_config_id, config_type, config_json FROM compute_config"):
        nid = f"config::{cfg['compute_config_id']}"
        attrs = safe_json(cfg['config_json'])
        config_text = f"Config Type: {cfg['config_type']}\n"
        for k, v in attrs.items():
            config_text += f"- {k}: {v}\n"
        nodes.append(GraphNode(nid, "config", cfg['compute_config_id'], config_text, attrs))

    # 3. Runs (with parent relationships)
    for run in c.execute("""
        SELECT run_id, resource_id, compute_config_id, parent_run_id, 
               status, started_at, ended_at, message, attributes_json 
        FROM run ORDER BY started_at DESC LIMIT 100
    """):
        nid = f"run::{run['run_id']}"
        duration_text = ""
        if run['started_at'] and run['ended_at']:
            # Could calculate duration here if needed
            duration_text = f"\nDuration: {run['started_at']} to {run['ended_at']}"
        
        nodes.append(GraphNode(
            nid, "run", f"Run {run['run_id']}", 
            f"Status: {run['status']}{duration_text}\nMessage: {run['message']}", 
            safe_json(run['attributes_json'])
        ))
        
        # Edges
        edges.append(GraphEdge(nid, f"resource::{run['resource_id']}", "run_of_resource", {}))
        
        if run['compute_config_id']:
            edges.append(GraphEdge(nid, f"config::{run['compute_config_id']}", "uses_config", {}))
        
        # Parent-child run relationships
        if run['parent_run_id']:
            edges.append(GraphEdge(f"run::{run['parent_run_id']}", nid, "triggers", {}))

    # 4. Run Dependencies (NEW)
    try:
        for dep in c.execute("""
            SELECT upstream_run_id, downstream_run_id, dependency_type 
            FROM run_dependency
        """):
            edges.append(GraphEdge(
                f"run::{dep['upstream_run_id']}", 
                f"run::{dep['downstream_run_id']}", 
                dep['dependency_type'] or "depends_on", 
                {}
            ))
    except sqlite3.OperationalError:
        pass  # Table doesn't exist

    # 5. DQ Failures
    for dq in c.execute("SELECT dq_result_id, run_id, status, message FROM dq_result WHERE status='FAIL' LIMIT 50"):
        nid = f"dq::{dq['dq_result_id']}"
        nodes.append(GraphNode(nid, "dq_result", "DQ Failure", f"Status: {dq['status']}\n{dq['message']}", {}))
        if dq['run_id']:
            edges.append(GraphEdge(nid, f"run::{dq['run_id']}", "dq_failed_in_run", {}))

    # 6. Incidents (Enhanced metadata)
    for inc in c.execute("SELECT incident_id, title, severity, status, summary, attributes_json FROM incident"):
        nid = f"incident::{inc['incident_id']}"
        attrs = safe_json(inc['attributes_json'])
        
        text = f"Incident: {inc['title']}\nSeverity: {inc['severity']}\nStatus: {inc['status']}\n{inc['summary']}"
        if 'mttr_target_minutes' in attrs:
            text += f"\nMTTR Target: {attrs['mttr_target_minutes']} min"
        if 'estimated_impact_usd' in attrs:
            text += f"\nEstimated Impact: ${attrs['estimated_impact_usd']:,}"
        
        nodes.append(GraphNode(nid, "incident", inc['title'], text, attrs))

    # 7. Incident Resource Links
    for link in c.execute("SELECT incident_id, resource_id, relation FROM incident_resource"):
        edges.append(GraphEdge(
            f"incident::{link['incident_id']}", 
            f"resource::{link['resource_id']}", 
            link['relation'], 
            {}
        ))

    # 8. Resource Owners (NEW)
    try:
        for owner in c.execute("""
            SELECT owner_id, resource_id, team_name, oncall_rotation, 
                   slack_channel, pagerduty_service_id, escalation_policy 
            FROM resource_owner
        """):
            nid = f"owner::{owner['owner_id']}"
            text = f"Team: {owner['team_name']}\n"
            text += f"Oncall: {owner['oncall_rotation'] or 'none'}\n"
            text += f"Slack: {owner['slack_channel'] or 'N/A'}\n"
            text += f"PagerDuty: {owner['pagerduty_service_id'] or 'N/A'}\n"
            text += f"Escalation: {owner['escalation_policy'] or 'standard'}"
            
            nodes.append(GraphNode(nid, "owner", owner['team_name'], text, {
                'team': owner['team_name'],
                'slack': owner['slack_channel'],
                'pagerduty': owner['pagerduty_service_id']
            }))
            
            edges.append(GraphEdge(
                f"resource::{owner['resource_id']}", 
                nid, 
                "owned_by", 
                {}
            ))
    except sqlite3.OperationalError:
        pass

    # 9. Resource Changes (NEW - Critical for "What changed?" queries)
    try:
        for change in c.execute("""
            SELECT change_id, resource_id, change_type, changed_by, 
                   change_summary, diff_json, changed_at 
            FROM resource_change 
            ORDER BY changed_at DESC LIMIT 100
        """):
            nid = f"change::{change['change_id']}"
            diff = safe_json(change['diff_json'])
            
            text = f"Change: {change['change_summary']}\n"
            text += f"Type: {change['change_type']}\n"
            text += f"By: {change['changed_by']}\n"
            text += f"When: {change['changed_at']}"
            
            nodes.append(GraphNode(nid, "change", change['change_summary'], text, diff))
            
            edges.append(GraphEdge(
                nid, 
                f"resource::{change['resource_id']}", 
                "changed", 
                {'change_type': change['change_type']}
            ))
    except sqlite3.OperationalError:
        pass

    # 10. Resource Baselines (NEW - For "Is this normal?" queries)
    try:
        for baseline in c.execute("""
            SELECT baseline_id, resource_id, metric_name, baseline_type, 
                   value_number, unit 
            FROM resource_baseline
        """):
            nid = f"baseline::{baseline['baseline_id']}"
            text = f"Baseline: {baseline['metric_name']} ({baseline['baseline_type']})\n"
            text += f"Value: {baseline['value_number']} {baseline['unit']}"
            
            nodes.append(GraphNode(nid, "baseline", f"{baseline['metric_name']} baseline", text, {
                'metric': baseline['metric_name'],
                'type': baseline['baseline_type'],
                'value': baseline['value_number']
            }))
            
            edges.append(GraphEdge(
                f"resource::{baseline['resource_id']}", 
                nid, 
                "has_baseline", 
                {}
            ))
    except sqlite3.OperationalError:
        pass

    # 11. SLA Policies (NEW)
    try:
        for sla in c.execute("""
            SELECT sla_id, resource_id, max_duration_seconds, max_cost_usd, 
                   availability_target, attributes_json 
            FROM sla_policy
        """):
            nid = f"sla::{sla['sla_id']}"
            attrs = safe_json(sla['attributes_json'])
            
            text = "SLA Policy\n"
            if sla['max_duration_seconds']:
                text += f"Max Duration: {sla['max_duration_seconds']/60:.0f} min\n"
            if sla['max_cost_usd']:
                text += f"Max Cost: ${sla['max_cost_usd']}\n"
            if sla['availability_target']:
                text += f"Availability: {sla['availability_target']*100:.2f}%\n"
            if 'business_impact' in attrs:
                text += f"Impact: {attrs['business_impact']}"
            
            nodes.append(GraphNode(nid, "sla", "SLA Policy", text, attrs))
            
            edges.append(GraphEdge(
                f"resource::{sla['resource_id']}", 
                nid, 
                "has_sla", 
                {}
            ))
    except sqlite3.OperationalError:
        pass

    # 12. Metrics (Increased limit, linked to resources and runs)
    metric_sql = """
    SELECT metric_point_id, resource_id, run_id, metric_name, value_number, unit, time 
    FROM metric_point 
    ORDER BY time DESC LIMIT 500
    """
    for m in c.execute(metric_sql):
        nid = f"metric::{m['metric_point_id']}"
        text = f"Metric: {m['metric_name']} = {m['value_number']} {m['unit'] or ''} @ {m['time']}"
        nodes.append(GraphNode(nid, "metric", m['metric_name'], text, {
            'value': m['value_number'],
            'unit': m['unit']
        }))
        
        if m['resource_id']:
            edges.append(GraphEdge(nid, f"resource::{m['resource_id']}", "metric_of_resource", {}))
        if m['run_id']:
            edges.append(GraphEdge(nid, f"run::{m['run_id']}", "metric_of_run", {}))

    # 13. Lineage Edges (from lineage_edge table)
    for lineage in c.execute("SELECT src_resource_id, dst_resource_id, relation_type FROM lineage_edge"):
        edges.append(GraphEdge(
            f"resource::{lineage['src_resource_id']}", 
            f"resource::{lineage['dst_resource_id']}", 
            lineage['relation_type'], 
            {}
        ))

    # 14. Cost Records (NEW - Link runs to costs)
    try:
        for cost in c.execute("""
            SELECT cost_id, run_id, resource_id, cost_usd, dbu, time, attributes_json 
            FROM cost_record 
            ORDER BY time DESC LIMIT 200
        """):
            nid = f"cost::{cost['cost_id']}"
            attrs = safe_json(cost['attributes_json'])
            
            text = f"Cost: ${cost['cost_usd']:.2f}"
            if cost['dbu']:
                text += f"\nDBU: {cost['dbu']}"
            text += f"\nTime: {cost['time']}"
            
            nodes.append(GraphNode(nid, "cost", f"Cost ${cost['cost_usd']:.2f}", text, attrs))
            
            if cost['run_id']:
                edges.append(GraphEdge(f"run::{cost['run_id']}", nid, "incurred_cost", {}))
            if cost['resource_id']:
                edges.append(GraphEdge(nid, f"resource::{cost['resource_id']}", "cost_of_resource", {}))
    except sqlite3.OperationalError:
        pass

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


# ---------------------------------------------------------------------------
# Neo4j ingestion
# ---------------------------------------------------------------------------

def ingest_reliability_graph_to_neo4j(
    db_path: str,
    uri: str,
    username: str,
    password: str,
    database: str = "neo4j",
) -> Tuple[int, int]:
    """
    Reads the reliability graph from SQLite and writes it into Neo4j.
    Clears all existing ReliabilityNode data before re-ingesting.
    Returns (node_count, edge_count).
    """
    from collections import defaultdict
    from neo4j import GraphDatabase

    nodes, edges = build_reliability_graph(db_path)

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        with driver.session(database=database) as session:
            # 1. Clear existing graph data
            session.run("MATCH (n:ReliabilityNode) DETACH DELETE n")

            # 2. Full-text index (idempotent)
            session.run("""
                CREATE FULLTEXT INDEX reliabilityFullText IF NOT EXISTS
                FOR (n:ReliabilityNode) ON EACH [n.title, n.text]
            """)

            # 3. Ingest nodes in one batched statement
            node_data = [
                {
                    "node_id":   n.id,
                    "node_type": n.type,
                    "title":     n.title,
                    "text":      n.text,
                    "attrs_json": json.dumps(n.attrs),
                }
                for n in nodes
            ]
            session.run(
                "UNWIND $nodes AS props CREATE (n:ReliabilityNode) SET n = props",
                nodes=node_data,
            )

            # 4. Ingest edges grouped by relationship type (avoids dynamic rel-type issue)
            edges_by_type: Dict[str, List[Dict[str, str]]] = defaultdict(list)
            for e in edges:
                rel = e.relation_type.upper().replace("-", "_").replace(" ", "_").replace(".", "_")
                edges_by_type[rel].append({"src": e.src, "dst": e.dst})

            for rel_type, pairs in edges_by_type.items():
                session.run(
                    f"UNWIND $pairs AS p "
                    f"MATCH (s:ReliabilityNode {{node_id: p.src}}) "
                    f"MATCH (d:ReliabilityNode {{node_id: p.dst}}) "
                    f"MERGE (s)-[:{rel_type}]->(d)",
                    pairs=pairs,
                )

    finally:
        driver.close()

    return len(nodes), len(edges)