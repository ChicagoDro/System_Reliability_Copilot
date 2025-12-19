# src/reports/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol
import pandas as pd

@dataclass
class SelectionLike:
    """
    Represents a clickable item in a report (e.g. a specific Incident or Resource).
    """
    entity_type: str  # e.g. "incident", "resource", "run"
    entity_id: str    # e.g. "inc_123", "res_abc"
    label: str        # e.g. "High Severity - Database Outage"


@dataclass
class Chip:
    """
    Represents a suggested action button (chip) shown when an item is selected.
    """
    id: str           # Unique ID for the button
    label: str        # Text on the button
    prompt: str       # The prompt sent to the LLM when clicked
    group: str = "Diagnose" # "Understand", "Diagnose", "Optimize", "Monitor"
    focus: bool = True # Whether this action implies focusing on the selected item


@dataclass
class ReportSpec:
    """
    Defines the structure and behavior of a specific report (e.g. Recent Incidents).
    """
    key: str
    name: str
    description: str
    
    # Function to load data from SQLite into a DataFrame
    # Signature: (db_path: str, filters: Dict) -> pd.DataFrame
    load_df: Callable[[str, Dict[str, Any]], pd.DataFrame]
    
    # Function to render the Streamlit visualization
    # Signature: (df: pd.DataFrame, filters: Dict) -> None
    render_viz: Callable[[pd.DataFrame, Dict[str, Any]], None]
    
    # Function to generate clickable selections from the data
    # Signature: (df: pd.DataFrame, filters: Dict) -> List[SelectionLike]
    build_selections: Callable[[pd.DataFrame, Dict[str, Any]], List[SelectionLike]]
    
    # Function to generate action chips for a specific selection
    # Signature: (selection: SelectionLike, filters: Dict) -> List[Chip]
    build_action_chips: Callable[[SelectionLike, Dict[str, Any]], List[Chip]]
    
    # Optional SQL query string for debugging display
    debug_sql: Optional[str] = None