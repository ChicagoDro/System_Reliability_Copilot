# src/prompts_deterministic.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class PromptStep:
    key: str
    prompt: str

@dataclass(frozen=True)
class PromptPack:
    name: str
    description: str
    steps: List[PromptStep]

PROMPT_PACKS: Dict[str, PromptPack] = {
    # --------------------------------------------------------------------------
    # 1. SLA & Performance
    # --------------------------------------------------------------------------
    "triage_sla_miss": PromptPack(
        name="SLA Miss Triage",
        description="Analyze a suspected SLA miss: timeline, cause, and mitigation.",
        steps=[
            PromptStep(
                key="timeline",
                prompt=(
                    "Build a precise timeline table (time | event | duration) for the selected run and any related errors.\n"
                    "Compare the duration against the historical average.\n"
                    "Did it fail fast, or hang for hours?"
                ),
            ),
            PromptStep(
                key="root_cause",
                prompt=(
                    "Based on the timeline and logs, what is the most likely root cause?\n"
                    "- Code (bug, infinite loop)?\n"
                    "- Data (volume spike, skew)?\n"
                    "- Infrastructure (capacity, network)?\n"
                    "Cite specific error messages or metrics."
                ),
            ),
            PromptStep(
                key="actions",
                prompt=(
                    "Suggest 3 concrete actions to prevent recurrence.\n"
                    "Consult the Runbooks to see if there is a known fix for this resource type."
                ),
            ),
        ],
    ),

    # --------------------------------------------------------------------------
    # 2. Cost Analysis
    # --------------------------------------------------------------------------
    "cost_anomaly_review": PromptPack(
        name="Cost Anomaly Review",
        description="Analyze a cost spike: drivers, trend, and optimization.",
        steps=[
            PromptStep(
                key="breakdown",
                prompt=(
                    "You are a FinOps analyst. Analyze the cost data for the selected resource.\n"
                    "Is the increase sudden (spike) or gradual (creep)?\n"
                    "Correlate the cost increase with run count or data volume if possible."
                ),
            ),
            PromptStep(
                key="optimization",
                prompt=(
                    "Consult Vendor Docs (Databricks/Snowflake/AWS) to recommend cost-saving measures.\n"
                    "Should we switch to Spot instances? Change the warehouse size? Use auto-termination?"
                ),
            ),
        ],
    ),

    # --------------------------------------------------------------------------
    # 3. Incident Response (Post-Mortem)
    # --------------------------------------------------------------------------
    "incident_postmortem": PromptPack(
        name="Draft Post-Mortem",
        description="Draft a formal incident report (Timeline, RCA, Action Items).",
        steps=[
            PromptStep(
                key="timeline",
                prompt=(
                    "Construct a detailed timeline of the incident:\n"
                    "- Detection Time (when did the alert fire?)\n"
                    "- Impact Start Time (when did metrics degrade?)\n"
                    "- Resolution Time (when did status return to normal?)\n"
                    "Use the retrieved telemetry."
                ),
            ),
            PromptStep(
                key="impact_analysis",
                prompt=(
                    "Assess the business impact.\n"
                    "Which downstream resources (tables, reports, services) were affected?\n"
                    "Were any SLAs breached?"
                ),
            ),
            PromptStep(
                key="rca_draft",
                prompt=(
                    "Draft the Root Cause Analysis (RCA) section.\n"
                    "Use the '5 Whys' technique if possible.\n"
                    "State clearly: Was this a code deployment, config change, or vendor outage?"
                ),
            ),
        ],
    ),

    # --------------------------------------------------------------------------
    # 4. Log Analysis (RCA)
    # --------------------------------------------------------------------------
    "log_root_cause_analysis": PromptPack(
        name="Log Root Cause Analysis",
        description="Deep dive into specific error logs to find the technical root cause.",
        steps=[
            PromptStep(
                key="explanation",
                prompt=(
                    "Analyze the selected log pattern. Explain the technical meaning of the error message.\n"
                    "Is this a syntax error, connection timeout, permission denied, or OOM?"
                ),
            ),
            PromptStep(
                key="solution_search",
                prompt=(
                    "Consult Vendor Docs and Runbooks for this specific error signature.\n"
                    "What is the standard fix? (e.g. increase memory, rotate credentials, rollback)."
                ),
            ),
        ],
    ),

    # --------------------------------------------------------------------------
    # 5. Resource Health (Failing Resources)
    # --------------------------------------------------------------------------
    "resource_health_check": PromptPack(
        name="Resource Health Check",
        description="Comprehensive health assessment for a failing resource.",
        steps=[
            PromptStep(
                key="failure_pattern",
                prompt=(
                    "Analyze the recent run history. Is the failure intermittent or continuous?\n"
                    "Did it start failing after a specific time (suggesting a bad deployment)?"
                ),
            ),
            PromptStep(
                key="dependencies",
                prompt=(
                    "Check upstream and downstream dependencies in the graph.\n"
                    "Did an upstream job fail? Is this resource blocking a critical downstream report?"
                ),
            ),
            PromptStep(
                key="recommendation",
                prompt=(
                    "Provide a final go/no-go recommendation:\n"
                    "- If code issue: Recommend Rollback.\n"
                    "- If data issue: Recommend Backfill.\n"
                    "- If infrastructure: Recommend Scaling."
                ),
            ),
        ],
    ),
}