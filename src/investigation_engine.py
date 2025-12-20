# src/investigation_engine.py
"""
Investigation Agent - Multi-hop reasoning engine for deep root cause analysis.

Executes structured investigation plans that gather evidence across the graph,
correlate signals, and produce SRE-grade insights with recommendations.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import json

@dataclass
class InvestigationStep:
    """A single step in an investigation workflow."""
    name: str
    description: str
    query: str
    graph_hops: int = 2
    use_runbooks: bool = False
    use_vendor_docs: bool = False
    node_types: Optional[List[str]] = None  # Filter to specific node types

@dataclass
class Evidence:
    """A piece of evidence collected during investigation."""
    step_name: str
    finding: str
    confidence: str  # HIGH, MEDIUM, LOW
    source_nodes: List[str]
    raw_data: Optional[Dict[str, Any]] = None

@dataclass
class Recommendation:
    """An actionable recommendation with cost-benefit."""
    option: str  # "Option A", "Option B"
    action: str
    cost_impact: str  # "$150/month", "$0", "Unknown"
    confidence: str  # HIGH, MEDIUM, LOW
    rationale: str

@dataclass
class Investigation:
    """Complete investigation result."""
    title: str
    summary: str
    timeline: List[Dict[str, str]]  # [{time, event}]
    evidence: List[Evidence]
    root_cause: str
    blast_radius: str
    cost_impact: str
    recommendations: List[Recommendation]
    prevention: str

# =============================================================================
# Investigation Plans (Templates)
# =============================================================================

PLAN_RUN_FAILURE = [
    InvestigationStep(
        name="failure_context",
        description="Get basic failure information",
        query="What is the run status, duration, and error message?",
        graph_hops=1,
    ),
    InvestigationStep(
        name="config_analysis",
        description="Check compute configuration",
        query="What compute config was used? What are the memory and CPU limits?",
        graph_hops=2,
        node_types=["config"],
    ),
    InvestigationStep(
        name="recent_changes",
        description="Find recent changes to this resource",
        query="What deployments or config changes happened in the last 7 days?",
        graph_hops=2,
        node_types=["change"],
    ),
    InvestigationStep(
        name="baseline_comparison",
        description="Compare against historical norms",
        query="How does this run's duration and resource usage compare to the baseline?",
        graph_hops=2,
        node_types=["baseline"],
    ),
    InvestigationStep(
        name="metric_correlation",
        description="Look for metric degradation before failure",
        query="What metrics spiked or degraded before the failure?",
        graph_hops=2,
        node_types=["metric"],
    ),
    InvestigationStep(
        name="log_analysis",
        description="Extract relevant error logs",
        query="What do the error logs say? Any warnings before the failure?",
        graph_hops=1,
    ),
    InvestigationStep(
        name="blast_radius",
        description="Find downstream impact",
        query="What downstream jobs or resources are blocked or affected?",
        graph_hops=3,
    ),
    InvestigationStep(
        name="cost_impact",
        description="Calculate financial impact",
        query="What was the cost of this failed run? What is the cost of downtime?",
        graph_hops=2,
        node_types=["cost", "sla"],
    ),
    InvestigationStep(
        name="runbook_guidance",
        description="Consult operational runbooks",
        query="What does the runbook recommend for this error type?",
        use_runbooks=True,
    ),
]

PLAN_COST_SPIKE = [
    InvestigationStep(
        name="cost_baseline",
        description="Establish cost baseline",
        query="What is the normal cost for this resource over the last 30 days?",
        graph_hops=2,
        node_types=["cost", "baseline"],
    ),
    InvestigationStep(
        name="spike_magnitude",
        description="Quantify the cost increase",
        query="How much did the cost increase? Is it a spike or gradual growth?",
        graph_hops=2,
        node_types=["cost"],
    ),
    InvestigationStep(
        name="run_frequency",
        description="Check if run frequency changed",
        query="Are we running more often than usual? Any failed retries?",
        graph_hops=2,
    ),
    InvestigationStep(
        name="config_changes",
        description="Look for cluster size changes",
        query="Did the cluster size or config change recently?",
        graph_hops=2,
        node_types=["change", "config"],
    ),
    InvestigationStep(
        name="data_volume",
        description="Check for data volume growth",
        query="Did the input data volume increase significantly?",
        graph_hops=2,
        node_types=["metric"],
    ),
    InvestigationStep(
        name="optimization_opportunities",
        description="Find waste and inefficiencies",
        query="What are the cost optimization opportunities for this resource?",
        use_runbooks=True,
    ),
]

PLAN_SLA_BREACH = [
    InvestigationStep(
        name="sla_definition",
        description="Get SLA target and business impact",
        query="What is the SLA target for this resource? What is the business impact?",
        graph_hops=2,
        node_types=["sla"],
    ),
    InvestigationStep(
        name="breach_magnitude",
        description="Quantify the breach",
        query="How much did we miss the SLA by? P50, P95, or max?",
        graph_hops=2,
        node_types=["baseline"],
    ),
    InvestigationStep(
        name="performance_regression",
        description="Identify what slowed down",
        query="What stage or step took longer than normal?",
        graph_hops=2,
        node_types=["metric"],
    ),
    InvestigationStep(
        name="trigger_analysis",
        description="Find the trigger",
        query="What changed that could have caused the slowdown?",
        graph_hops=2,
        node_types=["change"],
    ),
    InvestigationStep(
        name="escalation_policy",
        description="Determine who to notify",
        query="Who owns this resource? What is the escalation policy?",
        graph_hops=2,
        node_types=["owner", "sla"],
    ),
]

PLAN_DATA_QUALITY = [
    InvestigationStep(
        name="dq_failure_summary",
        description="Get DQ failure details",
        query="What data quality rule failed? What was the expected vs actual value?",
        graph_hops=1,
        node_types=["dq_result"],
    ),
    InvestigationStep(
        name="upstream_issues",
        description="Check upstream data sources",
        query="Did the upstream data source have issues? Schema changes?",
        graph_hops=3,
    ),
    InvestigationStep(
        name="schema_drift",
        description="Look for schema changes",
        query="Were there any schema changes upstream?",
        graph_hops=2,
        node_types=["change"],
    ),
    InvestigationStep(
        name="data_freshness",
        description="Check data freshness",
        query="Is the data stale? When was it last updated?",
        graph_hops=2,
        node_types=["metric"],
    ),
    InvestigationStep(
        name="historical_failures",
        description="Check if this is a recurring issue",
        query="Has this DQ rule failed before? How often?",
        graph_hops=2,
    ),
]

# =============================================================================
# Investigation Engine
# =============================================================================

class InvestigationEngine:
    """
    Executes investigation plans and produces structured analysis.
    
    Usage:
        engine = InvestigationEngine(assistant)
        investigation = engine.run(PLAN_RUN_FAILURE, focus={"entity_type": "run", "entity_id": "run_123"})
        print(investigation.summary)
    """
    
    def __init__(self, assistant):
        """
        Args:
            assistant: ReliabilityAssistant instance for executing queries
        """
        self.assistant = assistant
    
    def run(self, plan: List[InvestigationStep], focus: Optional[Dict[str, str]] = None) -> Investigation:
        """
        Execute an investigation plan and return structured results.
        
        Args:
            plan: List of InvestigationStep to execute
            focus: Entity context (e.g., {"entity_type": "run", "entity_id": "run_123"})
            
        Returns:
            Investigation object with findings and recommendations
        """
        evidence_list: List[Evidence] = []
        timeline: List[Dict[str, str]] = []
        
        # Execute each step
        for step in plan:
            # Add focus context to query if provided
            query = step.query
            if focus:
                query = f"{query}\nContext: {focus['entity_type']} = {focus['entity_id']}"
            
            # Execute query
            result = self.assistant.answer(query, focus=focus)
            
            # Parse result into evidence
            evidence = Evidence(
                step_name=step.name,
                finding=result.answer,
                confidence="HIGH",  # TODO: Implement confidence scoring
                source_nodes=[],  # TODO: Extract from graph_explanation
                raw_data={"llm_response": result.answer}
            )
            evidence_list.append(evidence)
        
        # Synthesize findings
        investigation = self._synthesize(evidence_list, focus)
        
        return investigation
    
    def _synthesize(self, evidence: List[Evidence], focus: Optional[Dict[str, str]]) -> Investigation:
        """
        Synthesize all evidence into a structured investigation report.
        """
        # TODO: Use LLM to synthesize evidence into structured output
        # For now, return a basic structure
        
        # Extract key findings
        failure_context = next((e for e in evidence if e.step_name == "failure_context"), None)
        changes = next((e for e in evidence if e.step_name == "recent_changes"), None)
        blast = next((e for e in evidence if e.step_name == "blast_radius"), None)
        cost = next((e for e in evidence if e.step_name == "cost_impact"), None)
        runbook = next((e for e in evidence if e.step_name == "runbook_guidance"), None)
        
        # Build investigation
        investigation = Investigation(
            title=f"Investigation: {focus.get('entity_id', 'Unknown') if focus else 'Unknown'}",
            summary="Multi-step root cause analysis completed.",
            timeline=[],  # TODO: Extract from evidence
            evidence=evidence,
            root_cause=changes.finding if changes else "Unknown",
            blast_radius=blast.finding if blast else "Unknown",
            cost_impact=cost.finding if cost else "Unknown",
            recommendations=[
                # TODO: Extract from runbook guidance
            ],
            prevention="TODO: Add prevention recommendations"
        )
        
        return investigation
    
    def format_markdown(self, investigation: Investigation) -> str:
        """Format investigation as markdown for display."""
        lines = [
            f"# {investigation.title}",
            "",
            f"**Summary**: {investigation.summary}",
            "",
            "## Root Cause",
            investigation.root_cause,
            "",
            "## Impact",
            f"- **Blast Radius**: {investigation.blast_radius}",
            f"- **Cost**: {investigation.cost_impact}",
            "",
            "## Evidence",
        ]
        
        for e in investigation.evidence:
            lines.append(f"### {e.step_name} ({e.confidence} confidence)")
            lines.append(e.finding)
            lines.append("")
        
        if investigation.recommendations:
            lines.append("## Recommendations")
            for i, rec in enumerate(investigation.recommendations, 1):
                lines.append(f"### {rec.option}")
                lines.append(f"**Action**: {rec.action}")
                lines.append(f"**Cost**: {rec.cost_impact}")
                lines.append(f"**Confidence**: {rec.confidence}")
                lines.append(f"**Rationale**: {rec.rationale}")
                lines.append("")
        
        lines.append("## Prevention")
        lines.append(investigation.prevention)
        
        return "\n".join(lines)


# =============================================================================
# Integration with Action Chips
# =============================================================================

def get_investigation_plan(chip_id: str, entity_type: str) -> Optional[List[InvestigationStep]]:
    """
    Map action chip IDs to investigation plans.
    
    Args:
        chip_id: The chip identifier (e.g., "res:debug")
        entity_type: The entity type (e.g., "run", "resource")
    
    Returns:
        Investigation plan or None
    """
    # Map chip patterns to plans
    if "debug" in chip_id or "failure" in chip_id:
        return PLAN_RUN_FAILURE
    
    if "cost" in chip_id or "spend" in chip_id:
        return PLAN_COST_SPIKE
    
    if "sla" in chip_id or "slow" in chip_id:
        return PLAN_SLA_BREACH
    
    if "dq" in chip_id or "quality" in chip_id:
        return PLAN_DATA_QUALITY
    
    return None
