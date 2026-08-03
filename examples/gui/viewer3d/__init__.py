"""Finger 3D Qt dashboard (mesh + UV arrows + force charts)."""

from .dashboard import FingerDashboardWindow, run_dashboard
from .layout import (
    LOG_PANEL,
    LAYOUT,
    MESH_CONTACT_ARROW,
    MESH_LIGHTING,
    PANEL_SETUP,
    TOP_ROW,
    DashboardLayout,
    MeshLighting,
    PanelRow,
    PanelSetup,
    PanelSlot,
    top_row_splitter_sizes,
    top_row_slot_index,
)

__all__ = [
    "DashboardLayout",
    "FingerDashboardWindow",
    "LAYOUT",
    "LOG_PANEL",
    "MESH_CONTACT_ARROW",
    "MESH_LIGHTING",
    "MeshLighting",
    "PANEL_SETUP",
    "TOP_ROW",
    "PanelRow",
    "PanelSetup",
    "PanelSlot",
    "run_dashboard",
    "top_row_splitter_sizes",
    "top_row_slot_index",
]
