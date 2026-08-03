"""Finger 3D mesh viewer with example-only contact and flow arrow overlays."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from orisys.finger.viewer import UVMeshViewer

from .contact_arrow import ContactArrowOverlay, ContactArrowStyle, DEFAULT_CONTACT_ARROW_STYLE
from .flow_arrow import DEFAULT_FLOW_ARROW_STYLE, FlowArrowOverlay, FlowArrowStyle


class FingerMeshViewer(UVMeshViewer):
    """UV mesh viewer with force-scaled contact arrow and flow tube arrows."""

    def __init__(
        self,
        mesh,
        *,
        max_magnitude=None,
        threshold: float = 0.0,
        color_mode: str = "flow",
        value_min=None,
        value_max=None,
        window_width: int = 1024,
        window_height: int = 1024,
        contact_arrow_style: ContactArrowStyle | None = None,
        normal_force_scale: float | None = None,
        show_contact_arrow: bool = True,
        flow_arrow_style: FlowArrowStyle | None = None,
        show_flow_arrows: bool = True,
    ):
        super().__init__(
            mesh,
            max_magnitude=max_magnitude,
            threshold=threshold,
            color_mode=color_mode,
            value_min=value_min,
            value_max=value_max,
            window_width=window_width,
            window_height=window_height,
        )
        self._contact_arrow = ContactArrowOverlay(
            mesh,
            style=contact_arrow_style or DEFAULT_CONTACT_ARROW_STYLE,
            normal_force_scale=normal_force_scale,
            enabled=show_contact_arrow,
        )
        style = flow_arrow_style or DEFAULT_FLOW_ARROW_STYLE
        if not show_flow_arrows:
            style = replace(style, enabled=False)
        self._flow_arrow = FlowArrowOverlay(mesh, style=style)

    def _extra_geometries(self):
        geoms = []
        if self._contact_arrow.arrow_mesh is not None:
            geoms.append(self._contact_arrow.arrow_mesh)
        if self._flow_arrow.enabled and self._flow_arrow.arrow_mesh is not None:
            geoms.append(self._flow_arrow.arrow_mesh)
        return geoms

    def _extra_geometries_for_init(self):
        return self._extra_geometries()

    def _extra_geometries_for_update(self):
        return self._extra_geometries()

    def update(
        self,
        flow=None,
        scalar_map=None,
        *,
        centroid=None,
        centroid_found: bool = False,
        fnormal: float = 0.0,
        valid_mask: np.ndarray | None = None,
    ):
        arrow = self._contact_arrow.compute(centroid, centroid_found, fnormal)
        if arrow is not None and self._contact_arrow.arrow_mesh is not None:
            arrow_vertices, _, arrow_colors = arrow
            self._contact_arrow.apply(arrow_vertices, arrow_colors)

        flow_result = self._flow_arrow.compute(flow, valid_mask=valid_mask)
        if flow_result is not None and self._flow_arrow.arrow_mesh is not None:
            flow_vertices, flow_triangles, flow_colors = flow_result
            self._flow_arrow.apply(flow_vertices, flow_triangles, flow_colors)

        return super().update(flow=flow, scalar_map=scalar_map)
