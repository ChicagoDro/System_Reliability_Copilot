# src/app.py
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st

from src.RAG_chatbot.chat_orchestrator import ReliabilityAssistant
from src.reports.base import SelectionLike
from src.reports.registry import get_reports, get_report_map, get_default_report_key
from src.RAG_chatbot.prompts_deterministic import PROMPT_PACKS
from src.RAG_chatbot.investigation_engine import (
    InvestigationEngine,
    get_investigation_plan,
    PLAN_RUN_FAILURE,
    PLAN_SLA_BREACH,
    PLAN_DATA_QUALITY
)


# ============================
# Deterministic Chip System
# ============================

@dataclass(frozen=True)
class Chip:
    """
    A deterministic, UI-stable action chip.
    """
    id: str
    label: str
    prompt: str
    focus: bool = True
    group: str = "Diagnose"
    investigation_plan: Optional[str] = None  # NEW: Link to investigation plan


GROUP_ORDER = ["Understand", "Diagnose", "Optimize", "Monitor"]


def _safe_slug(x: str) -> str:
    return (
        str(x)
        .replace(" ", "_")
        .replace("/", "_")
        .replace(":", "_")
        .replace("|", "_")
        .replace("\n", "_")
    )


def _default_chips_for_selection(report_name: str, sel: SelectionLike) -> List[Chip]:
    """
    Deterministic baseline chips that ALWAYS appear for a selection.
    Now includes Deep Dive investigation chips.
    """
    et = str(sel.entity_type)
    eid = str(sel.entity_id)
    report_slug = report_name.lower()

    base: List[Chip] = [
        Chip(
            id=f"core:about:{_safe_slug(et)}:{_safe_slug(eid)}",
            label="📌 Explain this",
            group="Understand",
            prompt=(
                f"Explain what this {et} ({eid}) represents in the system's telemetry, "
                f"and summarize what matters most in the context of the '{report_name}' report."
            ),
        ),
        Chip(
            id=f"core:drivers:{_safe_slug(et)}:{_safe_slug(eid)}",
            label="🧾 Main drivers",
            group="Diagnose",
            prompt=(
                f"For {et} ({eid}), identify the biggest drivers behind what I'm seeing in the '{report_name}' report. "
                "Be specific, and reference the underlying telemetry patterns (runs, compute usage, events) where applicable."
            ),
        ),
    ]

    # --- Deep Dive Investigation Chips ---
    
    # 1. Run failures
    if et == "run" or "fail" in report_slug or "error" in report_slug:
        base.append(Chip(
            id=f"investigate:run_failure:{_safe_slug(eid)}",
            label="🔬 Deep Dive (9 steps)",
            group="Diagnose",
            prompt="INVESTIGATE:run_failure",
            investigation_plan="run_failure",
            focus=True
        ))
    
    # 2. SLA breaches
    if "sla" in report_slug or "breach" in sel.label.lower():
        base.append(Chip(
            id=f"investigate:sla_breach:{_safe_slug(eid)}",
            label="🔬 SLA Analysis",
            group="Diagnose",
            prompt="INVESTIGATE:sla_breach",
            investigation_plan="sla_breach",
            focus=True
        ))
    
    # 4. Data quality
    if "dq" in report_slug or "quality" in report_slug or et == "dq_result":
        base.append(Chip(
            id=f"investigate:data_quality:{_safe_slug(eid)}",
            label="🔬 DQ Investigation",
            group="Diagnose",
            prompt="INVESTIGATE:data_quality",
            investigation_plan="data_quality",
            focus=True
        ))

    # --- Inject Prompt Packs ---
    
    if "sla" in report_slug or "breach" in sel.label.lower():
        if "triage_sla_miss" in PROMPT_PACKS:
            base.append(Chip(
                id=f"pack:sla:{_safe_slug(eid)}",
                label="🕵️ SLA Triage (Deep Dive)",
                group="Diagnose",
                prompt="PACK:triage_sla_miss",
                focus=True
            ))

    if "log" in report_slug or "error" in report_slug:
        if "log_root_cause_analysis" in PROMPT_PACKS:
            base.append(Chip(
                id=f"pack:log:{_safe_slug(eid)}",
                label="🔍 Root Cause Analysis",
                group="Diagnose",
                prompt="PACK:log_root_cause_analysis",
                focus=True
            ))

    if "failing" in report_slug or "fail" in report_slug:
        if "resource_health_check" in PROMPT_PACKS:
            base.append(Chip(
                id=f"pack:res:{_safe_slug(eid)}",
                label="🩺 Health Check (Deep Dive)",
                group="Diagnose",
                prompt="PACK:resource_health_check",
                focus=True
            ))

    return base


def _render_chip_row(chips: List[Chip], key_prefix: str, columns: int = 3) -> None:
    if not chips:
        return

    cols = st.columns(min(columns, len(chips)))
    for i, chip in enumerate(chips):
        with cols[i % len(cols)]:
            if st.button(chip.label, key=f"{key_prefix}:{chip.id}"):
                st.session_state.pending_prompt = chip.prompt
                st.session_state.pending_investigation = chip.investigation_plan
                st.rerun()


def _render_chip_groups(chips: List[Chip], key_prefix: str) -> None:
    if not chips:
        return

    grouped: Dict[str, List[Chip]] = {g: [] for g in GROUP_ORDER}
    for c in chips:
        g = c.group if c.group in grouped else "Diagnose"
        grouped[g].append(c)

    for g in GROUP_ORDER:
        if not grouped[g]:
            continue
        st.markdown(f"**{g}**")
        _render_chip_row(grouped[g], key_prefix=f"{key_prefix}:{g}", columns=3)


# ============================
# Report Catalog
# ============================

PILLAR_CATALOG: List[Tuple[str, str, List[str], List[Tuple[str, str]]]] = [
    (
        "Platform Health",
        "Resource status, run failures, and pipeline reliability.",
        ["Failing Resources", "SLA Breaches"],
        [("Zombie Resources", "Active resources with no recent runs.")],
    ),
    (
        "Observability",
        "Golden signals and infrastructure health.",
        ["Service Health (Golden Signals)"],
        [("Trace Latency", "P95 latency across distributed traces.")],
    ),
]

REPORT_NAME_ALIASES = {
    "Failing Resources": "🔥 Failing Resources",
    "SLA Breaches": "⏱️ SLA Breaches",
    "Service Health (Golden Signals)": "📡 Service Health",
}


def _resolve_report_key(identifier: str, report_map: Dict[str, object]) -> Optional[str]:
    if identifier in report_map:
        return identifier
    for k, r in report_map.items():
        if getattr(r, "name", None) == identifier:
            return k
    return None


def _display_report_name(report_obj: object) -> str:
    n = getattr(report_obj, "name", "Unknown Report")
    return REPORT_NAME_ALIASES.get(n, n)


def _build_uncategorized_report_names(report_map: Dict[str, object]) -> List[str]:
    categorized_names = set()
    for _, _, active_identifiers, _ in PILLAR_CATALOG:
        for ident in active_identifiers:
            categorized_names.add(ident)

    all_names = [getattr(r, "name", "") for r in report_map.values()]
    return sorted([n for n in all_names if n and n not in categorized_names])


def _select_report(key: str) -> None:
    st.session_state.selected_report_key = key
    st.session_state.pending_prompt = None
    st.session_state.pending_investigation = None
    st.session_state.selection = None
    st.session_state.commentary = []
    st.rerun()


def _render_sidebar_report_nav(report_map: Dict[str, object]) -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] .block-container { padding-top: 0.75rem; padding-bottom: 0.75rem; }
        .pillar-title { font-size: 0.95rem; font-weight: 700; margin: 0.25rem 0 0.10rem 0; }
        .pillar-sub { font-size: 0.75rem; opacity: 0.70; margin: 0 0 0.35rem 0; }
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
            width: 100%; border-radius: 10px; padding: 0.35rem 0.55rem; margin: 0.12rem 0;
            font-size: 0.80rem; text-align: left; white-space: normal !important; height: auto !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:disabled { opacity: 0.45; cursor: not-allowed; }
        .selected-report { font-size: 0.75rem; opacity: 0.75; margin-top: 0.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.header("Reports (Pillars)")
    q = st.text_input("Search reports", key="report_search", placeholder="e.g. incidents, reliability…")

    def matches(text: str) -> bool:
        return (not q) or (q.lower() in text.lower())

    for pillar, desc, active_idents, todo_items in PILLAR_CATALOG:
        if q and not matches(pillar) and not matches(desc):
            has_match = False
            for ident in active_idents:
                k = _resolve_report_key(ident, report_map)
                if k and matches(_display_report_name(report_map[k])): has_match = True
            if not has_match:
                for name, d in todo_items:
                    if matches(name) or matches(d): has_match = True
            if not has_match:
                continue

        st.markdown(f"<div class='pillar-title'>{pillar}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='pillar-sub'>{desc}</div>", unsafe_allow_html=True)

        for ident in active_idents:
            k = _resolve_report_key(ident, report_map)
            if not k: continue
            r = report_map[k]
            shown_name = _display_report_name(r)
            if q and not matches(shown_name): continue

            is_selected = (k == st.session_state.selected_report_key)
            label = f"✅ {shown_name}" if is_selected else shown_name
            if st.button(label, key=f"nav:{pillar}:{k}"): _select_report(k)

        for name, short_desc in todo_items:
            if q and not matches(name) and not matches(short_desc): continue
            st.button(f"🕒 {name} (TODO)", key=f"nav:{pillar}:todo:{_safe_slug(name)}", disabled=True)
        st.divider()

    uncat = _build_uncategorized_report_names(report_map)
    if uncat:
        st.markdown("<div class='pillar-title'>Uncategorized</div>", unsafe_allow_html=True)
        for name in uncat:
            k = _resolve_report_key(name, report_map)
            if not k: continue
            r = report_map[k]
            shown_name = _display_report_name(r)
            if q and not matches(shown_name): continue
            is_selected = (k == st.session_state.selected_report_key)
            label = f"✅ {shown_name}" if is_selected else shown_name
            if st.button(label, key=f"nav:uncat:{k}"): _select_report(k)
        st.divider()

    cur_key = st.session_state.selected_report_key
    cur_name = _display_report_name(report_map[cur_key]) if cur_key in report_map else cur_key
    st.markdown(f"<div class='selected-report'>Selected: <b>{cur_name}</b></div>", unsafe_allow_html=True)


# ============================
# App State / Assistant
# ============================

def init_state() -> None:
    if "assistant" not in st.session_state:
        st.session_state.assistant = ReliabilityAssistant.from_local()
    if "investigation_engine" not in st.session_state:
        st.session_state.investigation_engine = InvestigationEngine(st.session_state.assistant)
    if "selected_report_key" not in st.session_state:
        st.session_state.selected_report_key = get_default_report_key()
    if "filters" not in st.session_state:
        st.session_state.filters = {}
    if "selection" not in st.session_state:
        st.session_state.selection = None
    if "commentary" not in st.session_state:
        st.session_state.commentary = []
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None
    if "pending_investigation" not in st.session_state:
        st.session_state.pending_investigation = None
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    if "db_path" not in st.session_state:
        repo_root = Path(__file__).resolve().parents[1]
        default_db = repo_root / "data" / "reliability.db"
        st.session_state.db_path = os.getenv("DB_PATH", str(default_db))
    if "_debug_graph" not in st.session_state: st.session_state._debug_graph = None
    if "_debug_prompt" not in st.session_state: st.session_state._debug_prompt = None
    if "_debug_context" not in st.session_state: st.session_state._debug_context = None


def assistant() -> ReliabilityAssistant:
    return st.session_state.assistant


def investigation_engine() -> InvestigationEngine:
    return st.session_state.investigation_engine


def run_investigation(plan_name: str, focus: Optional[Dict[str, str]] = None) -> None:
    """
    Execute a multi-step investigation and display results progressively.
    """
    # Map plan name to actual plan
    plan_map = {
        "run_failure": PLAN_RUN_FAILURE,
        "sla_breach": PLAN_SLA_BREACH,
        "data_quality": PLAN_DATA_QUALITY,
    }
    
    plan = plan_map.get(plan_name)
    if not plan:
        st.error(f"Unknown investigation plan: {plan_name}")
        return
    
    # Create progress container
    progress_container = st.empty()
    results_container = st.empty()
    
    with progress_container.container():
        st.info(f"🔬 Starting {len(plan)} step investigation...")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Execute each step
    evidence_list = []
    for i, step in enumerate(plan):
        # Update progress
        progress = (i + 1) / len(plan)
        progress_bar.progress(progress)
        status_text.text(f"Step {i+1}/{len(plan)}: {step.description}")
        
        # Add focus context to query
        query = step.query
        if focus:
            query = f"{query}\nContext: {focus['entity_type']} = {focus['entity_id']}"
        
        # Execute query
        result = assistant().answer(query, focus=focus)
        
        # Store evidence
        evidence_list.append({
            "step": step.name,
            "description": step.description,
            "finding": result.answer,
            "timestamp": time.time()
        })
        
        # Brief pause for UX
        time.sleep(0.3)
    
    # Clear progress, show results
    progress_container.empty()
    
    # Format investigation report
    report_lines = [
        f"# 🔬 Investigation Report: {plan_name.replace('_', ' ').title()}",
        "",
        f"**Completed**: {len(plan)} steps",
        "",
        "---",
        ""
    ]
    
    for i, evidence in enumerate(evidence_list, 1):
        report_lines.append(f"## Step {i}: {evidence['description']}")
        report_lines.append("")
        report_lines.append(evidence['finding'])
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")
    
    report_md = "\n".join(report_lines)
    
    # Add to commentary
    st.session_state.commentary.append({
        "prompt": f"🔬 **Deep Dive Investigation**: {plan_name}",
        "response": report_md
    })


def run_commentary(prompt: str) -> None:
    focus = None
    sel = st.session_state.selection
    if sel is not None:
        focus = {"entity_type": sel.entity_type, "entity_id": sel.entity_id}

    # Check if this is an investigation request
    if prompt.startswith("INVESTIGATE:"):
        plan_name = prompt.split(":", 1)[1]
        run_investigation(plan_name, focus=focus)
        return

    # Handle Multi-Step Prompt Packs
    if prompt.startswith("PACK:"):
        pack_key = prompt.split(":", 1)[1]
        if pack_key in PROMPT_PACKS:
            pack = PROMPT_PACKS[pack_key]
            
            progress_msg = st.toast(f"🔎 Starting Deep Dive: {pack.name}...", icon="🚀")
            
            st.session_state.commentary.append({
                "prompt": f"**Executing Prompt Pack:** `{pack.name}`",
                "response": f"_{pack.description}_\n\nRunning {len(pack.steps)} analysis steps..."
            })
            
            for i, step in enumerate(pack.steps, 1):
                with st.spinner(f"Step {i}/{len(pack.steps)}: {step.key}..."):
                    result = assistant().answer(step.prompt, focus=focus)
                    
                    st.session_state.commentary.append({
                        "prompt": f"**Step {i}: {step.key}**", 
                        "response": result.answer
                    })
                    
                    if st.session_state.debug_mode:
                        st.session_state._debug_graph = result.graph_explanation
                        st.session_state._debug_prompt = result.llm_prompt
                        st.session_state._debug_context = result.llm_context
                    
                    time.sleep(0.5)
            
            progress_msg.toast(f"✅ Deep Dive Complete: {pack.name}", icon="🏁")
            return

    # Standard Single-Shot Prompt
    result = assistant().answer(prompt, focus=focus)
    st.session_state.commentary.append({"prompt": prompt, "response": result.answer})

    if st.session_state.debug_mode:
        st.session_state._debug_graph = result.graph_explanation
        st.session_state._debug_prompt = result.llm_prompt
        st.session_state._debug_context = result.llm_context
    else:
        st.session_state._debug_graph = None
        st.session_state._debug_prompt = None
        st.session_state._debug_context = None


def render_action_chips(report, sel: SelectionLike) -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] { width: 100%; }
        div[data-testid="stButton"] > button {
            width: 100%; border-radius: 999px; padding: 0.30rem 0.65rem; margin: 0.15rem 0;
            border: 1px solid rgba(49, 51, 63, 0.25); background-color: rgba(240, 242, 246, 0.6);
            font-size: 0.78rem; line-height: 1.05rem; font-weight: 500; white-space: normal !important;
            height: auto !important; text-align: center;
        }
        div[data-testid="stButton"] > button:hover {
            background-color: rgba(240, 242, 246, 0.9); border-color: rgba(49, 51, 63, 0.45);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    report_chips_raw = report.build_action_chips(sel, st.session_state.filters) or []

    report_chips: List[Chip] = []
    for idx, rc in enumerate(report_chips_raw):
        rc_id = getattr(rc, "id", None)
        stable_id = rc_id or f"report:{_safe_slug(report.key)}:{_safe_slug(sel.entity_type)}:{_safe_slug(sel.entity_id)}:{idx}"
        grp = getattr(rc, "group", None) or "Diagnose"
        inv_plan = getattr(rc, "investigation_plan", None)
        report_chips.append(Chip(
            id=stable_id, 
            label=rc.label, 
            prompt=rc.prompt, 
            focus=getattr(rc, "focus", True), 
            group=grp,
            investigation_plan=inv_plan
        ))

    core_chips = _default_chips_for_selection(report.name, sel)
    seen = set()
    combined: List[Chip] = []
    for c in (report_chips + core_chips):
        if c.id in seen: continue
        seen.add(c.id)
        combined.append(c)

    if not combined: return
    st.markdown("**Actions:**")
    _render_chip_groups(combined, key_prefix=f"chip:{report.key}")


# ============================
# Main Execution
# ============================

st.set_page_config(page_title="Reliability Copilot", page_icon="🛡️", layout="wide")
init_state()

reports = get_reports()
report_map = get_report_map()

if not report_map:
    st.error("No reports found! Please define reports in src/reports/registry.py.")
    st.stop()

if st.session_state.selected_report_key not in report_map:
    def_key = get_default_report_key()
    st.session_state.selected_report_key = def_key if (def_key and def_key in report_map) else list(report_map.keys())[0]

current_report = report_map[st.session_state.selected_report_key]

st.title("🛡️ Reliability Copilot")
st.caption("Deterministic reporting + contextual AI commentary + deep investigations")

with st.sidebar:
    _render_sidebar_report_nav(report_map)
    st.header("Controls")
    st.checkbox("Debug mode", key="debug_mode")
    st.caption(f"DB: `{st.session_state.db_path}`")
    if st.button("Clear selection"):
        st.session_state.selection = None
        st.session_state.commentary = []
        st.rerun()
    if st.button("Clear commentary"):
        st.session_state.commentary = []
        st.session_state.pending_prompt = None
        st.session_state.pending_investigation = None
        st.rerun()

viz_col, comm_col = st.columns([2.2, 1.0], gap="large")

with viz_col:
    st.subheader(current_report.name)
    st.caption(current_report.description)
    df = current_report.load_df(st.session_state.db_path, st.session_state.filters)
    current_report.render_viz(df, st.session_state.filters)
    selections = current_report.build_selections(df, st.session_state.filters)
    if selections:
        st.markdown("**Select an item:**")
        cols = st.columns(3)
        for i, sel in enumerate(selections):
            sel_key = f"select:{current_report.key}:{_safe_slug(sel.entity_type)}:{_safe_slug(sel.entity_id)}:{i}"
            with cols[i % 3]:
                if st.button(sel.label, key=sel_key):
                    st.session_state.selection = sel
                    st.session_state.commentary = []
                    st.session_state.pending_prompt = f"Tell me more about {sel.entity_type} {sel.entity_id}."
                    st.rerun()

with comm_col:
    st.subheader("Commentary")
    sel = st.session_state.selection
    if sel is None:
        st.info("Select an item in the report to generate commentary.")
    else:
        st.success(f"Selection: {sel.entity_type} • {sel.label}")
        render_action_chips(current_report, sel)
    
    st.markdown("---")
    if st.session_state.commentary:
        for item in st.session_state.commentary:
            with st.chat_message("user"):
                st.write(item["prompt"])
            with st.chat_message("assistant"):
                st.markdown(item["response"])
    else:
        st.caption("No commentary yet.")

    if st.session_state.debug_mode:
        with st.expander("🔍 Debug", expanded=False):
            if getattr(current_report, "debug_sql", None):
                st.markdown("**Report SQL**")
                st.code(current_report.debug_sql, language="sql")
            if st.session_state.commentary:
                if st.session_state._debug_graph:
                    st.markdown("**Graph / retrieval explanation**")
                    st.markdown(st.session_state._debug_graph)
                if st.session_state._debug_prompt:
                    st.markdown("**LLM prompt**")
                    st.code(st.session_state._debug_prompt)

    st.markdown("---")
    with st.form("freeform", clear_on_submit=False):
        free = st.text_area("Ask a follow-up", placeholder="Ask about this selection…", height=100, label_visibility="collapsed")
        submitted = st.form_submit_button("Ask")

    if submitted and free.strip():
        context = [f"Report: {current_report.name}"]
        if sel: context.append(f"Selected: {sel.entity_type} {sel.entity_id}")
        prompt = f"{free.strip()}\n\nContext:\n" + "\n".join(context)
        st.session_state.pending_prompt = prompt
        st.rerun()

# Execute pending prompts/investigations
if st.session_state.pending_investigation:
    plan_name = st.session_state.pending_investigation
    st.session_state.pending_investigation = None
    focus = None
    if st.session_state.selection:
        focus = {"entity_type": st.session_state.selection.entity_type, "entity_id": st.session_state.selection.entity_id}
    run_investigation(plan_name, focus)
    st.rerun()

if st.session_state.pending_prompt:
    p = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    run_commentary(p)
    st.rerun()
