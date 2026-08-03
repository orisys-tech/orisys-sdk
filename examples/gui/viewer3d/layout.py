"""
Finger dashboard layout — edit this file to define the panel hierarchy and sizes.

Structure:

    ┌─ toolbar ─────────────────────────────────────────────────────┐
    ├─ mesh ─┬─ charts ─┬─ settings ────────────────────────────────┤
    │        ├─ log ────┤                                         │
    └────────┴──────────┴─────────────────────────────────────────┘

Each panel uses explicit width_px and height_px.
charts_log_stretch / log_stretch control charts vs log height inside the charts column.

MeshLighting (below) controls the 3D mesh panel sun light:
  azimuth_deg     — horizontal angle in degrees (0° = +X, 90° = +Y)
  elevation_deg   — vertical angle in degrees (positive = from above)
  intensity       — Filament sun strength (typical 30000–120000)
  ambient/diffuse — Windows viewer shading weights (0–1)

MESH_BACKGROUND (below) sets the 3D mesh panel clear color (RGB 0–255).

MESH_AXIS_OVERLAY (below) controls the fixed top-right pre-rendered 3D axis triad:
  enabled, padding_px, size_px, opacity

MESH_CONTACT_ARROW (below) controls the yellow 3D contact arrow on the mesh panel:
  reference_normal_force — Fn at which arrow reaches full size (log/power/linear curve)
  force_strength_mode    — "log" | "power" | "linear"
  min/max_length_fraction, min/max_thickness_scale, color

Mesh panel has two sizes (edit MESH_RENDER_* and TOP_ROW mesh slot):
  display (TOP_ROW mesh width_px/height_px) — Qt widget size on screen
  render   (MESH_RENDER_WIDTH/HEIGHT)       — Open3D offscreen resolution (upscaled for display)

Performance (3D dashboard; edit DashboardLayout defaults):
  timer_interval_ms   — Qt timer period (16 ≈ 60 Hz tick rate)
  mesh_render_stride  — render 3D mesh every N frames (2 ≈ half mesh cost)
  chart_update_stride — update force charts every N frames
  mesh_async_render   — reserved for future use; mesh rendering currently stays on the UI thread

Edit TOP_ROW.slots to reorder or resize panels; set ``enabled=False`` to hide a panel (e.g. arrows).
Log sits under charts only (not under mesh). Settings is the rightmost column.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from gui.log_config import LOG_CONFIG, LogConfig
from viz.contact_arrow import ContactArrowStyle, DEFAULT_CONTACT_ARROW_STYLE
from viz.flow_arrow import FlowArrowStyle
from viz.render_2d import ArrowBackground, ArrowCanvasColors

PanelId = Literal["mesh", "arrows", "charts", "log", "settings"]


@dataclass(frozen=True)
class PanelSlot:
    """One panel in the dashboard."""

    id: PanelId
    title: str
    width_px: int
    height_px: int
    stretch: int = 0
    enabled: bool = True


@dataclass(frozen=True)
class PanelRow:
    """Horizontal row of panels (the top visual strip)."""

    slots: tuple[PanelSlot, ...]
    collapsible: bool = False


@dataclass(frozen=True)
class PanelSetup:
    """Full panel hierarchy: top row + log nested under charts."""

    top_row: PanelRow
    log_panel: PanelSlot
    charts_log_stretch: int = 5
    log_stretch: int = 1


# --- Top strip: mesh | arrows? | charts | settings (edit order and sizes here) ---
TOP_ROW = PanelRow(
    slots=(
        PanelSlot("mesh", "3D mesh", width_px=400, height_px=400),
        PanelSlot("arrows", "UV Unrolled", width_px=400, height_px=400, enabled=True),
        PanelSlot("charts", "Force charts", width_px=300, height_px=400),
        PanelSlot("settings", "Settings", width_px=250, height_px=0),
    ),
)

LOG_PANEL = PanelSlot("log", "Log", width_px=0, height_px=100)

PANEL_SETUP = PanelSetup(
    top_row=TOP_ROW,
    log_panel=LOG_PANEL,
    charts_log_stretch=5,
    log_stretch=1,
)

# Open3D offscreen resolution for the mesh panel (independent of on-screen widget size).
MESH_RENDER_WIDTH_PX = 500
MESH_RENDER_HEIGHT_PX = 500


@dataclass(frozen=True)
class MeshLighting:
    """3D mesh panel light — edit MESH_LIGHTING or DashboardLayout.mesh_lighting."""

    azimuth_deg: float = -45.0 # finger outline
    elevation_deg: float = -35.0 # tip to root
    intensity: float = 75000.0
    ambient: float = 0.35
    diffuse: float = 0.65

    @property
    def direction(self) -> tuple[float, float, float]:
        """Unit light direction derived from azimuth / elevation (degrees)."""
        az = math.radians(self.azimuth_deg)
        el = math.radians(self.elevation_deg)
        cos_el = math.cos(el)
        return (cos_el * math.cos(az), cos_el * math.sin(az), math.sin(el))


MESH_LIGHTING = MeshLighting(
    azimuth_deg=0,
    elevation_deg=0,
    intensity=75000.0,
    ambient=0.5,
    diffuse=0.5,
)


@dataclass(frozen=True)
class MeshBackground:
    """3D mesh panel clear color — edit MESH_BACKGROUND or DashboardLayout.mesh_background."""

    color: tuple[int, int, int] = (0, 0, 0)


MESH_BACKGROUND = MeshBackground(color=(0, 0, 0))


@dataclass(frozen=True)
class MeshAxisOverlay:
    """Fixed pre-rendered XYZ triad HUD on the 3D mesh RGB output."""

    enabled: bool = True
    padding_px: int = 12
    size_px: int = 96
    opacity: float = 1.0


MESH_AXIS_OVERLAY = MeshAxisOverlay()


# 3D mesh contact arrow — edit here for dashboard tuning (see ContactArrowStyle in viz/contact_arrow.py).
MESH_CONTACT_ARROW = ContactArrowStyle(
    reference_normal_force=10000.0,
    force_strength_mode="log",
    force_strength_gamma=0.5,
    min_length_fraction=0.02,
    max_length_fraction=0.30,
    min_thickness_scale=0.20,
    max_thickness_scale=1.0,
    normal_force_scale=1.0,
    color=(1.0, 0.92, 0.10),
)

# 3D mesh flow line arrows — tail_color/head_color are RGB 0–255 (see FlowArrowStyle).
MESH_FLOW_ARROW = FlowArrowStyle(
    threshold=2.0,
    grid_spacing=20,
    arrow_scale=0.5,
    length_margin=1.0,
    tail_color=(40, 100, 220),
    head_color=(40, 100, 220),
    head_fraction=0.5,
    opacity=1,
    line_width=15,
    head_line_width=30.0,
)

# UV arrow synthetic canvas — BGR tuples (outside valid_mask, inside valid_mask).
ARROW_CANVAS_COLORS = ArrowCanvasColors(
    outside_bgr=(0, 0, 0),
    uv_bgr=(128, 0, 0),
)


@dataclass(frozen=True)
class DashboardLayout:
    """Window chrome, chart styling, and panel hierarchy."""

    panel_setup: PanelSetup = PANEL_SETUP

    window_title: str = "Orisys Finger Dashboard"
    window_width: int = 1300
    window_height: int = 560

    root_margin_px: int = 6
    root_spacing_px: int = 6
    toolbar_spacing_px: int = 8

    plot_buffer_points: int = 120
    plot_sample_rate_hz: float = 30.0
    chart_title_font_pt: int = 11
    chart_axis_label_font_pt: int = 9
    chart_tick_font_pt: int = 9
    y_axis_min_span: float = 10000.0
    y_range_smooth_alpha: float = 0.5
    curve_color: str = "#00E5FF"

    # UV arrow panel: min flow magnitude to draw an arrow (display only; not dd02-ov.json contact.flow_threshold)
    arrow_flow_threshold: float = 1.0
    # "unrolled" = sensor texture; "pure_color" = solid canvas (tune colors via arrow_canvas_colors)
    arrow_background: ArrowBackground = "pure_color"
    arrow_canvas_colors: ArrowCanvasColors = ARROW_CANVAS_COLORS

    mesh_lighting: MeshLighting = MESH_LIGHTING
    mesh_background: MeshBackground = MESH_BACKGROUND
    mesh_contact_arrow: ContactArrowStyle = MESH_CONTACT_ARROW
    mesh_flow_arrow: FlowArrowStyle = MESH_FLOW_ARROW
    mesh_axis_overlay: MeshAxisOverlay = MESH_AXIS_OVERLAY

    log_config: LogConfig = LOG_CONFIG

    mesh_render_width_px: int = MESH_RENDER_WIDTH_PX
    mesh_render_height_px: int = MESH_RENDER_HEIGHT_PX

    timer_interval_ms: int = 16
    mesh_async_render: bool = False
    mesh_render_stride: int = 2
    chart_update_stride: int = 2

    def mesh_display_size(self) -> tuple[int, int]:
        """On-screen mesh panel size from TOP_ROW mesh slot."""
        slot = self.top_slot("mesh")
        return slot.width_px, slot.height_px

    def mesh_render_size(self) -> tuple[int, int]:
        """Open3D offscreen render target size (may differ from display size)."""
        return self.mesh_render_width_px, self.mesh_render_height_px

    def slot(self, panel_id: PanelId) -> PanelSlot | None:
        if self.panel_setup.log_panel.id == panel_id:
            return self.panel_setup.log_panel
        for slot in self.panel_setup.top_row.slots:
            if slot.id == panel_id:
                return slot
        return None

    def charts_column_height_px(self) -> int:
        """Total height of the charts column (charts + log when enabled)."""
        charts = self.top_slot("charts")
        height = charts.height_px
        log = self.panel_setup.log_panel
        if log.enabled and log.height_px > 0:
            height += log.height_px
        return height

    def top_slot(self, panel_id: PanelId) -> PanelSlot:
        for slot in self.panel_setup.top_row.slots:
            if slot.id == panel_id:
                return slot
        raise KeyError(f"panel {panel_id!r} not in top row")

    @property
    def mesh_panel_title(self) -> str:
        return self.top_slot("mesh").title

    @property
    def arrows_panel_title(self) -> str:
        return self.top_slot("arrows").title

    @property
    def settings_panel_title(self) -> str:
        return self.top_slot("settings").title


LAYOUT = DashboardLayout()


def top_row_splitter_sizes(layout: DashboardLayout = LAYOUT) -> tuple[int, ...]:
    """Horizontal splitter widths from panel setup."""
    return tuple(slot.width_px for slot in layout.panel_setup.top_row.slots if slot.enabled)


def top_row_slot_index(panel_id: PanelId, layout: DashboardLayout = LAYOUT) -> int:
    """Index of a panel in the horizontal top splitter."""
    for i, slot in enumerate(layout.panel_setup.top_row.slots):
        if slot.id == panel_id:
            return i
    raise KeyError(f"panel {panel_id!r} not in top row")
