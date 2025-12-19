# src/prompts_deterministic.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


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
    "triage_sla_miss": PromptPack(
        name="triage_sla_miss",
        description="Deterministic triage for a suspected SLA miss: what happened, why, impact, next actions.",
        steps=[
            PromptStep(
                key="summary",
                prompt=(
                    "You are an SRE-style reliability analyst.\n"
                    "Goal: deterministic incident triage.\n\n"
                    "1) Summarize the most relevant runs/metrics/logs/incidents for the given focus.\n"
                    "2) If there is an SLA breach signal, name it.\n"
                    "3) Provide timestamps.\n"
                    "Return markdown with headings:\n"
                    "## Executive summary\n"
                    "## Evidence timeline\n"
                    "## Most likely root cause\n"
                    "## Contributing factors\n"
                    "## Suggested next actions\n"
                    "## Sources\n"
                ),
            ),
            PromptStep(
                key="timeline",
                prompt=(
                    "Build a precise timeline table (time | signal | object_id | note) using only retrieved evidence.\n"
                    "Include runs, metrics, logs, incidents.\n"
                    "If time is missing, say 'unknown'.\n"
                    "Return only the markdown table, then a '## Sources' section."
                ),
            ),
            PromptStep(
                key="actions",
                prompt=(
                    "Based on the evidence, produce 5-10 concrete next actions.\n"
                    "Tag each as one of: [mitigation], [prevention], [observability], [cost], [process].\n"
                    "Return markdown bullets plus '## Sources'."
                ),
            ),
        ],
    ),
    "cost_anomaly_review": PromptPack(
        name="cost_anomaly_review",
        description="Deterministic cost spike analysis with likely drivers and fixes.",
        steps=[
            PromptStep(
                key="summary",
                prompt=(
                    "You are a FinOps reliability analyst.\n"
                    "Goal: deterministic cost anomaly review.\n\n"
                    "Return markdown with headings:\n"
                    "## Cost anomaly summary\n"
                    "## Evidence\n"
                    "## Likely drivers\n"
                    "## Recommended remediations\n"
                    "## Sources\n"
                ),
            ),
        ],
    ),
}
