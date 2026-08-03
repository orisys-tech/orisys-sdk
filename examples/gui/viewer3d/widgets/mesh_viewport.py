"""Embedded offscreen 3D mesh viewport for the Qt dashboard."""

from __future__ import annotations

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QMouseEvent

from pipeline.frame import FingerFrameView
from viz.offscreen_mesh import OffscreenFingerMeshRenderer

from ..layout import DashboardLayout, LAYOUT
from ..mesh_view_state import MeshViewState
from ..mesh_render_worker import MeshRenderWorker
from gui.widgets.qt_pixmap import ndarray_to_pixmap
from .image_panel import ImagePanel

_VIEW_ROTATE_SENSITIVITY = 0.35


class MeshViewportWidget(ImagePanel):
    """Render the finger mesh offscreen in a square 1:1 viewport."""

    def __init__(self, parent=None, *, layout: DashboardLayout = LAYOUT, mesh_state: MeshViewState | None = None):
        self._layout = layout
        self._mesh_state = mesh_state or MeshViewState.from_layout(layout)
        self._renderer: OffscreenFingerMeshRenderer | None = None
        self._mesh_worker: MeshRenderWorker | None = None
        self._mesh_map = "depth"
        self._threshold = 0.0
        self._enable_3d = True
        self._free_rotation = False
        self._dragging = False
        self._last_drag_pos = None
        self._last_frame: FingerFrameView | None = None
        display_w, display_h = layout.mesh_display_size()
        super().__init__(
            title=layout.mesh_panel_title,
            object_name="meshViewport",
            default_side=min(display_w, display_h),
            parent=parent,
        )
        self.label.installEventFilter(self)
        self.label.setMouseTracking(True)
        self._mesh_state.flow_arrows_changed.connect(self._on_flow_arrows_changed)

    def set_free_rotation(self, enabled: bool) -> None:
        self._free_rotation = bool(enabled)
        if not self._free_rotation:
            self._dragging = False
            self._last_drag_pos = None
        self.label.setCursor(Qt.OpenHandCursor if self._free_rotation else Qt.ArrowCursor)

    def _on_flow_arrows_changed(self, enabled: bool) -> None:
        if self._renderer is not None:
            self._renderer.flow_arrow.set_enabled(enabled)
        self._refresh_last_frame()

    def reset_view(self) -> None:
        if self._renderer is not None:
            self._renderer.reset_view()
        self._refresh_last_frame()

    def eventFilter(self, watched, event):
        if watched is self.label and self._free_rotation and self._renderer is not None:
            etype = event.type()
            if etype == QEvent.MouseButtonPress and isinstance(event, QMouseEvent):
                if event.button() == Qt.LeftButton:
                    self._dragging = True
                    self._last_drag_pos = event.pos()
                    self.label.setCursor(Qt.ClosedHandCursor)
                    return True
            elif etype == QEvent.MouseMove and isinstance(event, QMouseEvent):
                if self._dragging and self._last_drag_pos is not None:
                    delta = event.pos() - self._last_drag_pos
                    self._last_drag_pos = event.pos()
                    self._renderer.rotate_view(
                        delta.x() * _VIEW_ROTATE_SENSITIVITY,
                        delta.y() * _VIEW_ROTATE_SENSITIVITY,
                    )
                    self._refresh_last_frame()
                    return True
            elif etype == QEvent.MouseButtonRelease and isinstance(event, QMouseEvent):
                if event.button() == Qt.LeftButton and self._dragging:
                    self._dragging = False
                    self._last_drag_pos = None
                    self.label.setCursor(Qt.OpenHandCursor)
                    return True
        return super().eventFilter(watched, event)

    def configure(self, pipeline) -> None:
        self._mesh_map = pipeline.config.mesh_map
        self._threshold = pipeline.config.flow_threshold
        self._enable_3d = pipeline.config.enable_3d and pipeline.uv_mesh is not None
        self._stop_worker()
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
        if not self._enable_3d:
            self.label.setText(
                "3D mesh disabled" if not pipeline.config.enable_3d else "3D mesh unavailable"
            )
            self.set_source_pixmap(None)
            return
        self.label.setText("")
        self._init_renderer(pipeline)

    def _init_renderer(self, pipeline) -> None:
        if not self._enable_3d or pipeline.uv_mesh is None:
            return
        render_w, render_h = self._layout.mesh_render_size()
        self._renderer = OffscreenFingerMeshRenderer(
            pipeline.uv_mesh,
            width=render_w,
            height=render_h,
            threshold=self._threshold,
            color_mode=self._mesh_map,
            world_to_cam=pipeline.world_to_cam,
            lookat=pipeline.mesh_lookat,
            mesh_lighting=self._layout.mesh_lighting,
            mesh_background=self._layout.mesh_background.color,
            contact_arrow_style=self._layout.mesh_contact_arrow,
            flow_arrow_style=self._layout.mesh_flow_arrow,
            axis_overlay=self._layout.mesh_axis_overlay,
        )
        self._renderer.flow_arrow.set_enabled(self._mesh_state.flow_arrows_enabled)

    def _stop_worker(self) -> None:
        if self._mesh_worker is not None:
            self._mesh_worker.stop_worker()
            self._mesh_worker = None

    def on_side_length_changed(self, side: int) -> None:
        """Display widget resized; offscreen render size stays on layout.mesh_render_*."""
        del side  # display size only; ImagePanel upscales the pixmap to fit the label

    def _on_rgb_ready(self, rgb) -> None:
        self.set_source_pixmap(ndarray_to_pixmap(rgb, bgr=False))

    def _refresh_last_frame(self) -> None:
        if self._last_frame is None or self._renderer is None:
            return
        frame = self._last_frame
        rgb = self._renderer.render(
            flow=frame.flow,
            scalar_map=frame.depth_map,
            centroid=frame.centroid,
            centroid_found=frame.centroid_found,
            fnormal=frame.fnormal,
            valid_mask=frame.valid_mask,
        )
        self.set_source_pixmap(ndarray_to_pixmap(rgb, bgr=False))

    def update_frame(self, frame: FingerFrameView, *, async_render: bool | None = None) -> float:
        """Update mesh colors on the same thread that owns the renderer."""
        if not self._enable_3d or self._renderer is None:
            return 0.0

        self._last_frame = frame
        del async_render  # Offscreen Open3D renderers are not safe to drive from a QThread.

        import time

        t0 = time.perf_counter()
        rgb = self._renderer.render(
            flow=frame.flow,
            scalar_map=frame.depth_map,
            centroid=frame.centroid,
            centroid_found=frame.centroid_found,
            fnormal=frame.fnormal,
            valid_mask=frame.valid_mask,
        )
        self.set_source_pixmap(ndarray_to_pixmap(rgb, bgr=False))
        return (time.perf_counter() - t0) * 1000.0

    def close_renderer(self) -> None:
        self._stop_worker()
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
        self._last_frame = None
