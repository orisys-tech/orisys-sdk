"""UV flow-arrow panel for the Qt dashboard."""

from __future__ import annotations

import cv2

from pipeline.frame import FingerFrameView
from viz.render_2d import ArrowBackground, ArrowCanvasColors, render_uv_arrows

from ..layout import DashboardLayout, LAYOUT
from .image_panel import ImagePanel
from gui.widgets.qt_pixmap import ndarray_to_pixmap


class ArrowPanelWidget(ImagePanel):
    """UV unrolled flow-arrow panel."""

    def __init__(
        self,
        *,
        flow_threshold: float = 0.5,
        background: ArrowBackground = "unrolled",
        canvas_colors: ArrowCanvasColors | None = None,
        layout: DashboardLayout = LAYOUT,
        parent=None,
    ):
        slot = layout.top_slot("arrows")
        super().__init__(
            title=layout.arrows_panel_title,
            object_name="panelLabel",
            default_side=min(slot.width_px, slot.height_px),
            parent=parent,
        )
        self.flow_threshold = flow_threshold
        self.background = background
        self.canvas_colors = canvas_colors if canvas_colors is not None else layout.arrow_canvas_colors

    def set_flow_threshold(self, threshold: float) -> None:
        self.flow_threshold = threshold

    def set_background(self, background: ArrowBackground) -> None:
        self.background = background

    def update_frame(self, frame: FingerFrameView) -> None:
        arrows = render_uv_arrows(
            frame,
            flow_threshold=self.flow_threshold,
            background=self.background,
            canvas_colors=self.canvas_colors,
        )
        arrows = cv2.rotate(arrows, cv2.ROTATE_180)
        self.set_source_pixmap(ndarray_to_pixmap(arrows, bgr=True))
