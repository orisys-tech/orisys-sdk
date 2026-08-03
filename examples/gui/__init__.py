"""Public GUI entry points for Orisys example apps.

Two apps live under ``examples/gui``:

- Finger 3D dashboard: ``from gui import run_dashboard`` (also ``gui.viewer3d``)
- 2D sensor monitor: ``from gui.viewer2d import run_viewer``

Acquisition adapters (no widgets) live in ``gui.sensors``.
Shared bootstrap: ``gui.app``, ``gui.app_paths``, ``gui.log_config``, ``gui.widgets``.
"""

from .log_config import LOG_CONFIG, LogConfig
from .viewer3d import (
    FingerDashboardWindow,
    LAYOUT,
    LOG_PANEL,
    MESH_CONTACT_ARROW,
    MESH_LIGHTING,
    PANEL_SETUP,
    TOP_ROW,
    DashboardLayout,
    MeshLighting,
    PanelRow,
    PanelSetup,
    PanelSlot,
    run_dashboard,
    top_row_splitter_sizes,
    top_row_slot_index,
)
from viz.contact_arrow import ContactArrowStyle

__all__ = [
    "DashboardLayout",
    "FingerDashboardWindow",
    "LAYOUT",
    "LOG_CONFIG",
    "LOG_PANEL",
    "LogConfig",
    "MESH_CONTACT_ARROW",
    "MESH_LIGHTING",
    "ContactArrowStyle",
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
