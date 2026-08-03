"""Optical-flow arrow tubes on the finger UV surface mesh (TriangleMesh cylinders)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import cv2
import numpy as np

from orisys.finger.mesh import DEFAULT_SURFACE_COLOR, UVSurfaceMesh

from .contact_arrow import _rotation_matrix_z_to

# Grey mesh tone used to approximate opacity on backends without true alpha.
_MESH_GREY_RGB = np.asarray(DEFAULT_SURFACE_COLOR, dtype=np.float64)

# Maps style.line_width to tube radius as a fraction of mesh extent.
LINE_WIDTH_TO_SPAN_FRACTION = 0.0003
# Slight tail extension into the head segment to avoid visible gaps.
_TAIL_HEAD_OVERLAP_FRACTION = 0.03

SegmentRole = Literal["tail", "head"]

_CYLINDER_TEMPLATE_VERTICES: np.ndarray | None = None
_CYLINDER_TEMPLATE_TRIANGLES: np.ndarray | None = None
_CONE_TEMPLATE_VERTICES: np.ndarray | None = None
_CONE_TEMPLATE_TRIANGLES: np.ndarray | None = None
_CONE_APEX_AT_LOW_Z: bool | None = None


@dataclass(frozen=True)
class FlowArrowStyle:
    """Visual tuning for 3D mesh flow arrows (dashboard: edit MESH_FLOW_ARROW in layout.py).

    ``line_width`` / ``head_line_width`` scale tail and head tube radius relative to mesh extent.
    ``tail_color`` / ``head_color`` are RGB in 0–255 (same convention as OpenCV BGR tuples, but RGB order).
    """

    enabled: bool = True
    threshold: float = 1.0
    grid_spacing: int = 20
    arrow_scale: float = 0.5
    length_margin: float = 1.0
    tail_color: tuple[int, int, int] = (38, 235, 89)
    head_color: tuple[int, int, int] = (13, 115, 31)
    head_fraction: float = 0.25
    opacity: float = 0.65
    line_width: float = 2.0
    head_line_width: float = 3.0
    edge_margin: int = 8


DEFAULT_FLOW_ARROW_STYLE = FlowArrowStyle()


def _mesh_span(vertices: np.ndarray) -> float:
    extent = np.ptp(vertices, axis=0)
    return float(max(np.max(extent), 1e-6))


def segment_radius(mesh_span: float, line_width: float) -> float:
    """World-space tube radius from mesh extent and a width knob."""
    return mesh_span * max(float(line_width), 0.1) * LINE_WIDTH_TO_SPAN_FRACTION


def segment_radius_for_role(mesh_span: float, style: FlowArrowStyle, role: SegmentRole) -> float:
    width = style.line_width if role == "tail" else style.head_line_width
    return segment_radius(mesh_span, width)


def _prepare_uv_mask(valid_mask, shape: tuple[int, int]) -> np.ndarray | None:
    if valid_mask is None:
        return None
    h, w = shape
    mask = np.asarray(valid_mask, dtype=bool)
    if mask.shape != (h, w):
        mask_u8 = mask.astype(np.uint8)
        if mask_u8.ndim > 2:
            mask_u8 = mask_u8[:, :, 0]
        mask = cv2.resize(mask_u8, (w, h), interpolation=cv2.INTER_NEAREST).astype(bool)
    return mask


def _style_rgb01(style: FlowArrowStyle, role: SegmentRole) -> np.ndarray:
    rgb = np.asarray(style.tail_color if role == "tail" else style.head_color, dtype=np.float64).reshape(3)
    return np.clip(rgb / 255.0, 0.0, 1.0)


def effective_segment_color(
    style: FlowArrowStyle,
    role: SegmentRole,
    *,
    use_alpha_blend: bool = True,
) -> np.ndarray:
    """Return RGB in 0–1 for a tail or head segment."""
    rgb = _style_rgb01(style, role)
    if not use_alpha_blend:
        return rgb
    opacity = float(np.clip(style.opacity, 0.0, 1.0))
    return np.clip(opacity * rgb + (1.0 - opacity) * _MESH_GREY_RGB, 0.0, 1.0)


def _sample_flow_segments(
    world_xyz: np.ndarray,
    flow: np.ndarray,
    *,
    style: FlowArrowStyle = DEFAULT_FLOW_ARROW_STYLE,
    valid_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, list[SegmentRole]]:
    """Return segment start/end world points and role per segment (tail then head)."""
    empty = np.empty((0, 3), dtype=np.float64)
    if flow is None or np.asarray(flow).size == 0:
        return empty, empty, []

    flow = np.asarray(flow, dtype=np.float64)
    world_xyz = np.asarray(world_xyz, dtype=np.float64)
    h, w = flow.shape[:2]
    if world_xyz.shape[:2] != (h, w):
        return empty, empty, []

    grid_spacing = max(int(style.grid_spacing), 1)
    edge_margin = int(style.edge_margin)
    margin = float(style.length_margin)
    arrow_scale = max(float(style.arrow_scale), 1e-9)
    head_fraction = float(np.clip(style.head_fraction, 0.05, 0.95))
    tail_fraction = 1.0 - head_fraction

    rr = np.arange(grid_spacing // 2, h, grid_spacing)
    cc = np.arange(grid_spacing // 2, w, grid_spacing)
    rr, cc = np.meshgrid(rr, cc, indexing="ij")
    rr, cc = rr.reshape(-1), cc.reshape(-1)

    disp = 2.0 * flow[rr, cc, :]
    mag = np.linalg.norm(disp, axis=1)
    dx = disp[:, 0] / arrow_scale
    dy = disp[:, 1] / arrow_scale
    length = np.sqrt(dx * dx + dy * dy)
    scale = np.where(
        length > grid_spacing * margin,
        grid_spacing / np.maximum(length, 1e-9),
        1.0,
    ) * margin
    dx, dy = dx * scale, dy * scale
    end_x = np.clip(np.round(cc + dx).astype(np.int32), 0, w - 1)
    end_y = np.clip(np.round(rr + dy).astype(np.int32), 0, h - 1)

    valid = (
        (cc >= edge_margin)
        & (cc < w - edge_margin)
        & (rr >= edge_margin)
        & (rr < h - edge_margin)
        & (mag >= float(style.threshold))
    )

    mask = _prepare_uv_mask(valid_mask, (h, w))
    if mask is not None:
        valid &= mask[rr, cc]
        valid &= mask[end_y, end_x]

    if not np.any(valid):
        return empty, empty, []

    starts = world_xyz[rr[valid], cc[valid]]
    ends = world_xyz[end_y[valid], end_x[valid]]
    finite = np.all(np.isfinite(starts), axis=1) & np.all(np.isfinite(ends), axis=1)
    if not np.any(finite):
        return empty, empty, []

    starts = starts[finite]
    ends = ends[finite]
    non_zero = np.linalg.norm(ends - starts, axis=1) > 1e-9
    if not np.any(non_zero):
        return empty, empty, []

    starts = starts[non_zero]
    ends = ends[non_zero]
    junctions = starts + tail_fraction * (ends - starts)

    seg_starts = np.vstack((starts, junctions))
    seg_ends = np.vstack((junctions, ends))
    n = len(starts)
    roles: list[SegmentRole] = ["tail"] * n + ["head"] * n
    return seg_starts, seg_ends, roles


def build_flow_arrow_lines(
    world_xyz: np.ndarray,
    flow: np.ndarray,
    *,
    style: FlowArrowStyle = DEFAULT_FLOW_ARROW_STYLE,
    valid_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build line indices for flow arrows (used by tests and debugging)."""
    empty_pts = np.empty((0, 3), dtype=np.float64)
    empty_lines = np.empty((0, 2), dtype=np.int32)
    empty_colors = np.empty((0, 3), dtype=np.float64)

    seg_starts, seg_ends, roles = _sample_flow_segments(
        world_xyz, flow, style=style, valid_mask=valid_mask
    )
    if len(seg_starts) == 0:
        return empty_pts, empty_lines, empty_colors

    points = np.empty((len(seg_starts) * 2, 3), dtype=np.float64)
    points[0::2] = seg_starts
    points[1::2] = seg_ends
    lines = np.column_stack(
        (np.arange(0, len(points), 2, dtype=np.int32), np.arange(1, len(points), 2, dtype=np.int32))
    )
    line_colors = np.vstack(
        [effective_segment_color(style, role, use_alpha_blend=True) for role in roles]
    )
    return points, lines, line_colors


def _cylinder_template(o3d):
    global _CYLINDER_TEMPLATE_VERTICES, _CYLINDER_TEMPLATE_TRIANGLES
    if _CYLINDER_TEMPLATE_VERTICES is None:
        cyl = o3d.geometry.TriangleMesh.create_cylinder(
            radius=1.0,
            height=1.0,
            resolution=8,
            split=1,
        )
        _CYLINDER_TEMPLATE_VERTICES = np.asarray(cyl.vertices, dtype=np.float64)
        _CYLINDER_TEMPLATE_TRIANGLES = np.asarray(cyl.triangles, dtype=np.int32)
    return _CYLINDER_TEMPLATE_VERTICES, _CYLINDER_TEMPLATE_TRIANGLES


def _cone_apex_at_low_z(vertices: np.ndarray) -> bool:
    """True when the cone tip is on the low-z side of the Open3D template."""
    radii = np.linalg.norm(vertices[:, :2], axis=1)
    apex_z = float(vertices[np.argmin(radii), 2])
    z_mid = 0.5 * (float(vertices[:, 2].min()) + float(vertices[:, 2].max()))
    return apex_z < z_mid


def _cone_template(o3d):
    global _CONE_TEMPLATE_VERTICES, _CONE_TEMPLATE_TRIANGLES, _CONE_APEX_AT_LOW_Z
    if _CONE_TEMPLATE_VERTICES is None:
        cone = o3d.geometry.TriangleMesh.create_cone(
            radius=1.0,
            height=1.0,
            resolution=8,
            split=1,
        )
        _CONE_TEMPLATE_VERTICES = np.asarray(cone.vertices, dtype=np.float64)
        _CONE_TEMPLATE_TRIANGLES = np.asarray(cone.triangles, dtype=np.int32)
        _CONE_APEX_AT_LOW_Z = _cone_apex_at_low_z(_CONE_TEMPLATE_VERTICES)
    return _CONE_TEMPLATE_VERTICES, _CONE_TEMPLATE_TRIANGLES


def _transform_axis_segment(
    template_vertices: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    radius: float,
    *,
    apex_at_end: bool = False,
) -> np.ndarray:
    """Place a +Z template from ``start`` to ``end`` (axis anchored, not midpoint-centered).

    Open3D cylinders are centered on the origin; cone apex side is detected from the template.
    ``apex_at_end=True`` maps the template apex to ``end`` (flow tip); base to ``start``.
    """
    direction = np.asarray(end, dtype=np.float64) - np.asarray(start, dtype=np.float64)
    length = float(np.linalg.norm(direction))
    if length <= 1e-9 or radius <= 0.0:
        return np.empty((0, 3), dtype=np.float64)

    dir_hat = direction / length
    rotation = _rotation_matrix_z_to(dir_hat)
    scaled = np.asarray(template_vertices, dtype=np.float64).copy()

    z_min = float(scaled[:, 2].min())
    z_max = float(scaled[:, 2].max())
    z_span = z_max - z_min
    if z_span <= 1e-9:
        return np.empty((0, 3), dtype=np.float64)

    if apex_at_end:
        t = (z_max - scaled[:, 2]) / z_span * length
    else:
        t = (scaled[:, 2] - z_min) / z_span * length

    radial = np.column_stack((scaled[:, 0] * radius, scaled[:, 1] * radius, t))
    return radial @ rotation.T + np.asarray(start, dtype=np.float64)


def _transform_cylinder_segment(
    template_vertices: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    radius: float,
) -> np.ndarray:
    return _transform_axis_segment(template_vertices, start, end, radius)


def build_flow_arrow_mesh(
    world_xyz: np.ndarray,
    flow: np.ndarray,
    mesh_span: float,
    *,
    style: FlowArrowStyle = DEFAULT_FLOW_ARROW_STYLE,
    valid_mask: np.ndarray | None = None,
    o3d=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build merged mesh flow arrows: cylinder tail + cone head per arrow."""
    empty_v = np.empty((0, 3), dtype=np.float64)
    empty_t = np.empty((0, 3), dtype=np.int32)
    empty_c = np.empty((0, 3), dtype=np.float64)

    seg_starts, seg_ends, roles = _sample_flow_segments(
        world_xyz, flow, style=style, valid_mask=valid_mask
    )
    if len(seg_starts) == 0:
        return empty_v, empty_t, empty_c

    if o3d is None:
        import open3d as o3d

    cyl_vertices, cyl_triangles = _cylinder_template(o3d)
    cone_vertices, cone_triangles = _cone_template(o3d)

    vertices_parts: list[np.ndarray] = []
    triangles_parts: list[np.ndarray] = []
    colors_parts: list[np.ndarray] = []
    vertex_offset = 0

    for start, end, role in zip(seg_starts, seg_ends, roles):
        seg_start = np.asarray(start, dtype=np.float64)
        seg_end = np.asarray(end, dtype=np.float64)
        axis = seg_end - seg_start
        seg_len = float(np.linalg.norm(axis))
        if seg_len <= 1e-9:
            continue

        radius = segment_radius_for_role(mesh_span, style, role)
        if role == "tail":
            template_vertices, template_triangles = cyl_vertices, cyl_triangles
            apex_at_end = False
            overlap = _TAIL_HEAD_OVERLAP_FRACTION * seg_len
            seg_end = seg_end + (axis / seg_len) * overlap
        else:
            template_vertices, template_triangles = cone_vertices, cone_triangles
            apex_at_end = not bool(_CONE_APEX_AT_LOW_Z)
            tail_radius = segment_radius_for_role(mesh_span, style, "tail")
            radius = max(radius, tail_radius)

        verts = _transform_axis_segment(
            template_vertices,
            seg_start,
            seg_end,
            radius,
            apex_at_end=apex_at_end,
        )
        if verts.size == 0:
            continue
        color = effective_segment_color(style, role, use_alpha_blend=True)
        vertices_parts.append(verts)
        triangles_parts.append(template_triangles + vertex_offset)
        colors_parts.append(np.tile(color, (len(verts), 1)))
        vertex_offset += len(verts)

    if not vertices_parts:
        return empty_v, empty_t, empty_c

    return (
        np.vstack(vertices_parts),
        np.vstack(triangles_parts),
        np.vstack(colors_parts),
    )


def create_flow_mesh_geometry(o3d):
    """Create a persistent Open3D mesh for the flow arrow overlay."""
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(np.empty((0, 3), dtype=np.float64))
    mesh.triangles = o3d.utility.Vector3iVector(np.empty((0, 3), dtype=np.int32))
    mesh.vertex_colors = o3d.utility.Vector3dVector(np.empty((0, 3), dtype=np.float64))
    mesh.compute_vertex_normals()
    return mesh


class FlowArrowOverlay:
    """Example-layer flow arrows as cylinder tail + cone head meshes on the UV surface."""

    def __init__(
        self,
        mesh: UVSurfaceMesh,
        *,
        style: FlowArrowStyle | None = None,
    ):
        import open3d as o3d

        self.mesh = mesh
        self.style = style or DEFAULT_FLOW_ARROW_STYLE
        self._enabled = bool(self.style.enabled)
        self._mesh_span = _mesh_span(mesh.rest_vertices)
        _cylinder_template(o3d)
        _cone_template(o3d)
        self.arrow_mesh = create_flow_mesh_geometry(o3d) if self._enabled else None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled and self.arrow_mesh is None:
            import open3d as o3d

            self.arrow_mesh = create_flow_mesh_geometry(o3d)

    def compute(
        self,
        flow,
        valid_mask: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        if not self._enabled or self.arrow_mesh is None:
            return None

        return build_flow_arrow_mesh(
            self.mesh.world_xyz,
            flow,
            self._mesh_span,
            style=self.style,
            valid_mask=valid_mask,
        )

    def apply(self, arrow_vertices: np.ndarray, arrow_triangles: np.ndarray, arrow_colors: np.ndarray) -> None:
        """Update the persistent flow mesh geometry in place."""
        import open3d as o3d

        self.arrow_mesh.vertices = o3d.utility.Vector3dVector(arrow_vertices.astype(np.float64))
        self.arrow_mesh.triangles = o3d.utility.Vector3iVector(arrow_triangles.astype(np.int32))
        self.arrow_mesh.vertex_colors = o3d.utility.Vector3dVector(arrow_colors.astype(np.float64))
        self.arrow_mesh.compute_vertex_normals()


FLOW_ARROWS_GEOMETRY_NAME = "flow_arrows"


@dataclass
class FlowArrowFilamentSlot:
    added: bool = False


@dataclass
class FlowArrowHiddenSlot:
    in_vis: bool = False


def ensure_flow_arrow_in_hidden_vis(
    overlay: FlowArrowOverlay,
    vis,
    slot: FlowArrowHiddenSlot,
) -> None:
    """Add flow-arrow geometry to a HiddenVisualizer window when enabled at init."""
    if overlay.enabled and overlay.arrow_mesh is not None and not slot.in_vis:
        vis.add_geometry(overlay.arrow_mesh)
        slot.in_vis = True


def update_flow_arrows_filament(
    overlay: FlowArrowOverlay,
    flow,
    valid_mask,
    *,
    scene,
    material,
    slot: FlowArrowFilamentSlot,
    mesh_to_o3d: Callable,
) -> None:
    """Sync flow-arrow TriangleMesh geometry to a Filament offscreen scene."""
    flow_result = overlay.compute(flow, valid_mask=valid_mask)
    if not overlay.enabled:
        if slot.added:
            scene.remove_geometry(FLOW_ARROWS_GEOMETRY_NAME)
            slot.added = False
        return
    if flow_result is None or overlay.arrow_mesh is None:
        return

    flow_vertices, flow_triangles, flow_colors = flow_result
    if len(flow_vertices) > 0:
        flow_mesh = mesh_to_o3d(flow_vertices, flow_triangles, flow_colors)
        if not slot.added:
            scene.add_geometry(FLOW_ARROWS_GEOMETRY_NAME, flow_mesh, material)
            slot.added = True
        else:
            scene.remove_geometry(FLOW_ARROWS_GEOMETRY_NAME)
            scene.add_geometry(FLOW_ARROWS_GEOMETRY_NAME, flow_mesh, material)
    elif slot.added:
        scene.remove_geometry(FLOW_ARROWS_GEOMETRY_NAME)
        slot.added = False


def update_flow_arrows_hidden(
    overlay: FlowArrowOverlay,
    flow,
    valid_mask,
    *,
    vis,
    slot: FlowArrowHiddenSlot,
) -> None:
    """Sync flow-arrow TriangleMesh geometry to a HiddenVisualizer window."""
    flow_result = overlay.compute(flow, valid_mask=valid_mask)
    if not overlay.enabled:
        if slot.in_vis and overlay.arrow_mesh is not None:
            empty = np.empty((0, 3), dtype=np.float64)
            empty_i = np.empty((0, 3), dtype=np.int32)
            overlay.apply(empty, empty_i, empty)
            vis.update_geometry(overlay.arrow_mesh)
        return
    if overlay.arrow_mesh is None:
        return
    if not slot.in_vis:
        vis.add_geometry(overlay.arrow_mesh)
        slot.in_vis = True
    if flow_result is not None:
        flow_vertices, flow_triangles, flow_colors = flow_result
        overlay.apply(flow_vertices, flow_triangles, flow_colors)
        vis.update_geometry(overlay.arrow_mesh)

