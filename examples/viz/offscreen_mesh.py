"""Embedded Open3D mesh renderer for Qt dashboards (offscreen or hidden-window capture)."""

from __future__ import annotations

import sys

import numpy as np

from orisys.finger.mesh import UVSurfaceMesh
from orisys.finger.viewer import flow_magnitude_vertex_colors, scalar_map_vertex_colors

from .contact_arrow import ContactArrowOverlay
from .flow_arrow import (
    FlowArrowFilamentSlot,
    FlowArrowHiddenSlot,
    FlowArrowOverlay,
    ensure_flow_arrow_in_hidden_vis,
    update_flow_arrows_filament,
    update_flow_arrows_hidden,
)
from .mesh_camera import (
    apply_filament_sun_light,
    apply_shade_factors,
    apply_view_from_world_to_cam,
    camera_look_at_from_world_to_cam,
    default_look_at_view,
    orbit_eye_about_target,
    precompute_shade_factors,
)


def _numpy_o3d_image_to_rgb(image) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        if arr.dtype == np.float32 or arr.dtype == np.float64:
            return (np.clip(arr[:, :, :3], 0.0, 1.0) * 255.0).astype(np.uint8)
        return arr[:, :, :3].astype(np.uint8)
    return arr.astype(np.uint8)


def _make_lit_material(o3d):
    material = o3d.visualization.rendering.MaterialRecord()
    material.shader = "defaultLit"
    material.base_color = (1.0, 1.0, 1.0, 1.0)
    return material


def _shade_vertex_colors(mesh, colors: np.ndarray, shade_factors) -> np.ndarray:
    return apply_shade_factors(colors, shade_factors)


def _mesh_to_o3d(o3d, vertices: np.ndarray, triangles: np.ndarray, colors: np.ndarray):
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(vertices.astype(np.float64))
    mesh.triangles = o3d.utility.Vector3iVector(triangles.astype(np.int32))
    mesh.vertex_colors = o3d.utility.Vector3dVector(colors.astype(np.float64))
    mesh.compute_vertex_normals()
    return mesh


def _vertex_colors(mesh, *, color_mode, threshold, value_min, value_max, flow=None, scalar_map=None):
    if color_mode == "depth":
        return scalar_map_vertex_colors(
            scalar_map,
            mesh,
            value_min=value_min,
            value_max=value_max,
            threshold=threshold,
        )
    return flow_magnitude_vertex_colors(
        flow,
        mesh,
        threshold=threshold,
    )



def _background_rgba01(color: tuple[int, int, int]) -> list[float]:
    r, g, b = (int(color[0]), int(color[1]), int(color[2]))
    return [r / 255.0, g / 255.0, b / 255.0, 1.0]


def _background_rgb01(color: tuple[int, int, int]) -> np.ndarray:
    return np.asarray(_background_rgba01(color)[:3], dtype=np.float64)


# Cached pre-rendered mesh-axis triads keyed by size_px.
_AXIS_TRIAD_CACHE: dict[int, np.ndarray] = {}


def _project_mesh_axis_to_screen(point_xyz: np.ndarray, *, size_px: int) -> tuple[int, int, float]:
    """Project mesh coords to HUD pixels.

    Screen mapping for the fixed mesh-axis reference:
      +X -> down, +Y -> left, +Z -> inward (into the page).

    Mild foreshortening keeps +Z visible as a short into-page axis.
    Returns (px, py, depth) where larger depth is farther from the viewer.
    """
    x, y, z = float(point_xyz[0]), float(point_xyz[1]), float(point_xyz[2])
    # Camera looks predominantly along +Z (into page): u right, v down.
    # Soft shear so Z has a short foreshortened stub.
    shear = 0.34
    u = -y - shear * z
    v = x - shear * z
    scale = size_px * 0.30
    # Origin slightly lower-right-of-center so labeled tips stay in-frame.
    cx = size_px * 0.58
    cy = size_px * 0.48
    return int(round(cx + u * scale)), int(round(cy + v * scale)), z


def _render_axis_triad_rgba(size_px: int) -> np.ndarray:
    """Build (and cache) a transparent RGBA 3D-looking XYZ triad."""
    import cv2

    size_px = max(48, int(size_px))
    cached = _AXIS_TRIAD_CACHE.get(size_px)
    if cached is not None:
        return cached

    rgba = np.zeros((size_px, size_px, 4), dtype=np.uint8)
    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3]

    # Soft circular plate for contrast on bright contact heatmaps.
    plate = np.zeros((size_px, size_px), dtype=np.uint8)
    center = (size_px // 2, size_px // 2)
    radius = int(size_px * 0.46)
    cv2.circle(plate, center, radius, 255, thickness=-1, lineType=cv2.LINE_AA)
    rgba[:, :, 0:3][plate > 0] = (18, 18, 18)
    alpha[plate > 0] = 140

    thickness = max(2, size_px // 42)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.35, size_px / 220.0)
    origin = np.zeros(3, dtype=np.float64)
    o_xy = _project_mesh_axis_to_screen(origin, size_px=size_px)[:2]

    axes = (
        ("X", np.array([1.0, 0.0, 0.0]), (230, 70, 70)),
        ("Y", np.array([0.0, 1.0, 0.0]), (70, 210, 95)),
        ("Z", np.array([0.0, 0.0, 1.0]), (70, 140, 255)),
    )
    # Paint far axes first so nearer shafts occlude correctly.
    painted = []
    for label, direction, color in axes:
        tip = direction * 1.0
        px, py, depth = _project_mesh_axis_to_screen(tip, size_px=size_px)
        painted.append((depth, label, color, (px, py)))
    painted.sort(key=lambda item: item[0], reverse=True)

    layer = np.zeros((size_px, size_px, 3), dtype=np.uint8)
    for _, label, color, tip_xy in painted:
        cv2.arrowedLine(
            layer,
            o_xy,
            tip_xy,
            color,
            thickness,
            line_type=cv2.LINE_AA,
            tipLength=0.28,
        )
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, max(1, thickness - 1))
        # Offset label slightly past the arrow tip, away from origin.
        dx = tip_xy[0] - o_xy[0]
        dy = tip_xy[1] - o_xy[1]
        norm = max(1.0, float(np.hypot(dx, dy)))
        lx = int(tip_xy[0] + 8 * dx / norm - tw // 2)
        ly = int(tip_xy[1] + 8 * dy / norm + th // 2)
        lx = min(max(1, lx), size_px - tw - 1)
        ly = min(max(th + 1, ly), size_px - 2)
        cv2.putText(
            layer,
            label,
            (lx, ly),
            font,
            font_scale,
            color,
            max(1, thickness - 1),
            cv2.LINE_AA,
        )
    # Origin hub on the same contiguous buffer.
    cv2.circle(layer, o_xy, max(2, thickness), (235, 235, 235), -1, lineType=cv2.LINE_AA)

    mask = np.any(layer > 0, axis=2)
    rgb[mask] = layer[mask]
    alpha[mask] = 255

    _AXIS_TRIAD_CACHE[size_px] = rgba
    return rgba


def draw_axis_overlay(
    rgb: np.ndarray,
    *,
    enabled: bool = True,
    padding_px: int = 12,
    size_px: int = 96,
    opacity: float = 1.0,
) -> np.ndarray:
    """Composite a fixed top-right mesh-axis triad onto an RGB frame.

    The triad is pre-rendered and cached; orientation is locked to true mesh
    axes (+X down, +Y left, +Z inward) and does not follow free-rotate.
    """
    if not enabled or rgb is None or rgb.size == 0:
        return rgb

    out = np.ascontiguousarray(rgb)
    if out.ndim != 3 or out.shape[2] < 3:
        return out

    triad = _render_axis_triad_rgba(size_px)
    th, tw = triad.shape[:2]
    pad = max(0, int(padding_px))
    h, w = out.shape[:2]
    x0 = max(0, w - tw - pad)
    y0 = max(0, pad)
    x1 = min(w, x0 + tw)
    y1 = min(h, y0 + th)
    if x1 <= x0 or y1 <= y0:
        return out

    roi = out[y0:y1, x0:x1]
    overlay = triad[: y1 - y0, : x1 - x0]
    alpha = (overlay[:, :, 3].astype(np.float32) / 255.0) * float(np.clip(opacity, 0.0, 1.0))
    if alpha.ndim == 2:
        alpha = alpha[:, :, None]
    rgb_o = overlay[:, :, :3].astype(np.float32)
    base = roi.astype(np.float32)
    blended = rgb_o * alpha + base * (1.0 - alpha)
    roi[:] = np.clip(blended, 0, 255).astype(np.uint8)
    return out


def _apply_axis_overlay(rgb: np.ndarray, axis_overlay) -> np.ndarray:
    if axis_overlay is None:
        return draw_axis_overlay(rgb)
    return draw_axis_overlay(
        rgb,
        enabled=bool(getattr(axis_overlay, "enabled", True)),
        padding_px=int(getattr(axis_overlay, "padding_px", 12)),
        size_px=int(getattr(axis_overlay, "size_px", 96)),
        opacity=float(getattr(axis_overlay, "opacity", 1.0)),
    )


class _FilamentOffscreenBackend:
    """Filament OffscreenRenderer (Linux headless / platforms with EGL)."""

    def __init__(
        self,
        mesh: UVSurfaceMesh,
        *,
        width: int,
        height: int,
        threshold: float,
        color_mode: str,
        value_min,
        value_max,
        world_to_cam: np.ndarray | None,
        lookat: np.ndarray,
        show_contact_arrow: bool,
        mesh_lighting=None,
        mesh_background: tuple[int, int, int] = (0, 0, 0),
        contact_arrow_style=None,
        flow_arrow_style=None,
        axis_overlay=None,
    ):
        import open3d as o3d

        self._o3d = o3d
        self.mesh = mesh
        self.width = width
        self.height = height
        self.threshold = threshold
        self.color_mode = color_mode
        self.value_min = value_min
        self.value_max = value_max
        self.world_to_cam = world_to_cam
        self.lookat = lookat
        self.mesh_lighting = mesh_lighting
        self.mesh_background = mesh_background
        self.axis_overlay = axis_overlay
        self._shade_factors = (
            precompute_shade_factors(mesh.rest_vertices, mesh.triangles, mesh_lighting)
            if mesh_lighting is not None
            else None
        )
        self._contact_arrow = ContactArrowOverlay(
            mesh,
            enabled=show_contact_arrow,
            style=contact_arrow_style,
        )
        self._flow_arrow = FlowArrowOverlay(mesh, style=flow_arrow_style)
        self._renderer = o3d.visualization.rendering.OffscreenRenderer(self.width, self.height)
        self._renderer.scene.set_background(_background_rgba01(self.mesh_background))
        if mesh_lighting is not None:
            apply_filament_sun_light(
                self._renderer,
                direction=mesh_lighting.direction,
                intensity=mesh_lighting.intensity,
            )
        self._material = _make_lit_material(o3d)
        self._mesh_added = False
        self._arrow_added = False
        self._flow_arrow_slot = FlowArrowFilamentSlot()
        self._reset_view_state()
        self._apply_camera()

    def _reset_view_state(self) -> None:
        if self.world_to_cam is not None:
            center, eye, up = camera_look_at_from_world_to_cam(self.world_to_cam, lookat=self.lookat)
        else:
            center, eye, up = default_look_at_view(self.mesh.rest_vertices, self.lookat)
        self._view_center = center
        self._view_eye = eye
        self._view_up = up

    def _apply_camera(self) -> None:
        self._renderer.scene.camera.look_at(self._view_center, self._view_eye, self._view_up)

    def rotate_view(self, dx: float, dy: float) -> None:
        self._view_eye, self._view_up = orbit_eye_about_target(
            self._view_center,
            self._view_eye,
            self._view_up,
            dx,
            dy,
        )
        self._apply_camera()

    def reset_view(self) -> None:
        self._reset_view_state()
        self._apply_camera()

    def resize(self, width: int, height: int) -> None:
        width = max(int(width), 64)
        height = max(int(height), 64)
        if width == self.width and height == self.height:
            return
        self.width = width
        self.height = height
        self._renderer = self._o3d.visualization.rendering.OffscreenRenderer(self.width, self.height)
        self._renderer.scene.set_background(_background_rgba01(self.mesh_background))
        if self.mesh_lighting is not None:
            apply_filament_sun_light(
                self._renderer,
                direction=self.mesh_lighting.direction,
                intensity=self.mesh_lighting.intensity,
            )
        self._material = _make_lit_material(self._o3d)
        self._mesh_added = False
        self._arrow_added = False
        self._flow_arrow_slot = FlowArrowFilamentSlot()
        center, eye, up = self._view_center, self._view_eye, self._view_up
        self._renderer = self._o3d.visualization.rendering.OffscreenRenderer(self.width, self.height)
        self._renderer.scene.set_background(_background_rgba01(self.mesh_background))
        if self.mesh_lighting is not None:
            apply_filament_sun_light(
                self._renderer,
                direction=self.mesh_lighting.direction,
                intensity=self.mesh_lighting.intensity,
            )
        self._material = _make_lit_material(self._o3d)
        self._view_center, self._view_eye, self._view_up = center, eye, up
        self._apply_camera()

    def render(
        self,
        *,
        flow=None,
        scalar_map=None,
        centroid=None,
        centroid_found=False,
        fnormal=0.0,
        valid_mask=None,
    ):
        o3d = self._o3d
        colors = _vertex_colors(
            self.mesh,
            color_mode=self.color_mode,
            threshold=self.threshold,
            value_min=self.value_min,
            value_max=self.value_max,
            flow=flow,
            scalar_map=scalar_map,
        )
        body_mesh = _mesh_to_o3d(o3d, self.mesh.rest_vertices, self.mesh.triangles, colors)

        if not self._mesh_added:
            self._renderer.scene.add_geometry("finger_mesh", body_mesh, self._material)
            self._mesh_added = True
        else:
            self._renderer.scene.remove_geometry("finger_mesh")
            self._renderer.scene.add_geometry("finger_mesh", body_mesh, self._material)

        arrow_result = self._contact_arrow.compute(centroid, centroid_found, fnormal)
        if arrow_result is not None and self._contact_arrow.arrow_mesh is not None:
            arrow_vertices, arrow_triangles, arrow_colors = arrow_result
            if np.any(arrow_vertices):
                arrow_mesh = _mesh_to_o3d(o3d, arrow_vertices, arrow_triangles, arrow_colors)
                if not self._arrow_added:
                    self._renderer.scene.add_geometry("contact_arrow", arrow_mesh, self._material)
                    self._arrow_added = True
                else:
                    self._renderer.scene.remove_geometry("contact_arrow")
                    self._renderer.scene.add_geometry("contact_arrow", arrow_mesh, self._material)
            elif self._arrow_added:
                self._renderer.scene.remove_geometry("contact_arrow")
                self._arrow_added = False

        update_flow_arrows_filament(
            self._flow_arrow,
            flow,
            valid_mask,
            scene=self._renderer.scene,
            material=self._material,
            slot=self._flow_arrow_slot,
            mesh_to_o3d=lambda v, t, c: _mesh_to_o3d(o3d, v, t, c),
        )

        rgb = _numpy_o3d_image_to_rgb(self._renderer.render_to_image())
        return _apply_axis_overlay(rgb, self.axis_overlay)

    def close(self) -> None:
        self._renderer = None


class _HiddenVisualizerBackend:
    """Invisible Open3D Visualizer + framebuffer capture (Windows-friendly)."""

    def __init__(
        self,
        mesh: UVSurfaceMesh,
        *,
        width: int,
        height: int,
        threshold: float,
        color_mode: str,
        value_min,
        value_max,
        world_to_cam: np.ndarray | None,
        lookat: np.ndarray,
        show_contact_arrow: bool,
        mesh_lighting=None,
        mesh_background: tuple[int, int, int] = (0, 0, 0),
        contact_arrow_style=None,
        flow_arrow_style=None,
        axis_overlay=None,
    ):
        import open3d as o3d

        self._o3d = o3d
        self.mesh = mesh
        self.width = width
        self.height = height
        self.threshold = threshold
        self.color_mode = color_mode
        self.value_min = value_min
        self.value_max = value_max
        self.world_to_cam = world_to_cam
        self.lookat = lookat
        self.mesh_lighting = mesh_lighting
        self.mesh_background = mesh_background
        self.axis_overlay = axis_overlay
        self._shade_factors = (
            precompute_shade_factors(mesh.rest_vertices, mesh.triangles, mesh_lighting)
            if mesh_lighting is not None
            else None
        )
        self._contact_arrow = ContactArrowOverlay(
            mesh,
            enabled=show_contact_arrow,
            style=contact_arrow_style,
        )
        self._flow_arrow = FlowArrowOverlay(mesh, style=flow_arrow_style)
        self.vis = None
        self.tri_mesh = None
        self._flow_arrow_slot = FlowArrowHiddenSlot()
        self._create_window()

    def _create_window(self) -> None:
        o3d = self._o3d
        if self.vis is not None:
            self.vis.destroy_window()

        colors = _vertex_colors(
            self.mesh,
            color_mode=self.color_mode,
            threshold=self.threshold,
            value_min=self.value_min,
            value_max=self.value_max,
        )
        colors = _shade_vertex_colors(self.mesh, colors, self._shade_factors)
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window(
            window_name="Orisys Finger Mesh (embedded)",
            width=self.width,
            height=self.height,
            visible=False,
        )

        self.tri_mesh = o3d.geometry.TriangleMesh()
        self.tri_mesh.vertices = o3d.utility.Vector3dVector(self.mesh.rest_vertices.astype(np.float64))
        self.tri_mesh.triangles = o3d.utility.Vector3iVector(self.mesh.triangles.astype(np.int32))
        self.tri_mesh.vertex_colors = o3d.utility.Vector3dVector(colors.astype(np.float64))
        self.tri_mesh.compute_vertex_normals()
        self.vis.add_geometry(self.tri_mesh)

        if self._contact_arrow.arrow_mesh is not None:
            self.vis.add_geometry(self._contact_arrow.arrow_mesh)

        ensure_flow_arrow_in_hidden_vis(self._flow_arrow, self.vis, self._flow_arrow_slot)

        render_option = self.vis.get_render_option()
        render_option.mesh_show_back_face = True
        render_option.background_color = _background_rgb01(self.mesh_background)
        if hasattr(render_option, "light_on"):
            render_option.light_on = False

        self._apply_default_view()

    def _apply_default_view(self) -> None:
        if self.vis is None:
            return
        if self.world_to_cam is not None:
            apply_view_from_world_to_cam(self.vis, self.world_to_cam, lookat=self.lookat)
        else:
            view_control = self.vis.get_view_control()
            center, eye, up = default_look_at_view(self.mesh.rest_vertices, self.lookat)
            view_control.set_lookat(center)
            front = center - eye
            front_norm = float(np.linalg.norm(front))
            if front_norm > 1e-9:
                front = front / front_norm
            else:
                front = np.array([0.0, 0.0, -1.0], dtype=np.float64)
            view_control.set_front(front)
            view_control.set_up(up)
            extent = np.ptp(self.mesh.rest_vertices, axis=0)
            span = float(np.max(extent))
            view_control.set_zoom(0.5 if span > 0 else 0.7)

        self.vis.poll_events()
        self.vis.update_renderer()

    def rotate_view(self, dx: float, dy: float) -> None:
        if self.vis is None:
            return
        self.vis.get_view_control().rotate(float(dx), float(dy))
        self.vis.poll_events()
        self.vis.update_renderer()

    def reset_view(self) -> None:
        if self.vis is None:
            return
        self._apply_default_view()

    def resize(self, width: int, height: int) -> None:
        width = max(int(width), 64)
        height = max(int(height), 64)
        if width == self.width and height == self.height:
            return
        self.width = width
        self.height = height
        self._create_window()

    def render(
        self,
        *,
        flow=None,
        scalar_map=None,
        centroid=None,
        centroid_found=False,
        fnormal=0.0,
        valid_mask=None,
    ):
        o3d = self._o3d
        colors = _vertex_colors(
            self.mesh,
            color_mode=self.color_mode,
            threshold=self.threshold,
            value_min=self.value_min,
            value_max=self.value_max,
            flow=flow,
            scalar_map=scalar_map,
        )
        colors = _shade_vertex_colors(self.mesh, colors, self._shade_factors)

        self.tri_mesh.vertex_colors = o3d.utility.Vector3dVector(colors.astype(np.float64))
        self.vis.update_geometry(self.tri_mesh)

        arrow_result = self._contact_arrow.compute(centroid, centroid_found, fnormal)
        if arrow_result is not None and self._contact_arrow.arrow_mesh is not None:
            arrow_vertices, _, arrow_colors = arrow_result
            self._contact_arrow.apply(arrow_vertices, arrow_colors)
            self.vis.update_geometry(self._contact_arrow.arrow_mesh)

        update_flow_arrows_hidden(
            self._flow_arrow,
            flow,
            valid_mask,
            vis=self.vis,
            slot=self._flow_arrow_slot,
        )

        self.vis.poll_events()
        self.vis.update_renderer()
        rgb = _numpy_o3d_image_to_rgb(self.vis.capture_screen_float_buffer(do_render=False))
        return _apply_axis_overlay(rgb, self.axis_overlay)

    def close(self) -> None:
        if self.vis is not None:
            self.vis.destroy_window()
            self.vis = None


def _create_backend(mesh: UVSurfaceMesh, **kwargs):
    # Filament OffscreenRenderer needs EGL headless (not available on Windows).
    if sys.platform == "win32":
        return _HiddenVisualizerBackend(mesh, **kwargs)
    try:
        return _FilamentOffscreenBackend(mesh, **kwargs)
    except RuntimeError:
        return _HiddenVisualizerBackend(mesh, **kwargs)

class OffscreenFingerMeshRenderer:
    """Render finger UV mesh + contact/flow arrows to an RGB image for Qt embedding."""

    def __init__(
        self,
        mesh: UVSurfaceMesh,
        *,
        width: int = 512,
        height: int = 512,
        threshold: float = 0.0,
        color_mode: str = "depth",
        value_min=None,
        value_max=None,
        world_to_cam: np.ndarray | None = None,
        lookat: np.ndarray | None = None,
        show_contact_arrow: bool = True,
        mesh_lighting=None,
        mesh_background: tuple[int, int, int] = (0, 0, 0),
        contact_arrow_style=None,
        flow_arrow_style=None,
        axis_overlay=None,
    ):
        lookat = lookat if lookat is not None else mesh.rest_vertices.mean(axis=0)
        self._backend = _create_backend(
            mesh,
            width=int(width),
            height=int(height),
            threshold=threshold,
            color_mode=color_mode,
            value_min=value_min,
            value_max=value_max,
            world_to_cam=world_to_cam,
            lookat=lookat,
            show_contact_arrow=show_contact_arrow,
            mesh_lighting=mesh_lighting,
            mesh_background=mesh_background,
            contact_arrow_style=contact_arrow_style,
            flow_arrow_style=flow_arrow_style,
            axis_overlay=axis_overlay,
        )

    @property
    def width(self) -> int:
        return self._backend.width

    @property
    def height(self) -> int:
        return self._backend.height

    def resize(self, width: int, height: int) -> None:
        self._backend.resize(width, height)

    def rotate_view(self, dx: float, dy: float) -> None:
        rotate = getattr(self._backend, "rotate_view", None)
        if rotate is not None:
            rotate(dx, dy)

    def reset_view(self) -> None:
        reset = getattr(self._backend, "reset_view", None)
        if reset is not None:
            reset()

    @property
    def flow_arrow(self) -> FlowArrowOverlay:
        return self._backend._flow_arrow

    def render(
        self,
        *,
        flow=None,
        scalar_map=None,
        centroid=None,
        centroid_found: bool = False,
        fnormal: float = 0.0,
        valid_mask=None,
    ) -> np.ndarray:
        return self._backend.render(
            flow=flow,
            scalar_map=scalar_map,
            centroid=centroid,
            centroid_found=centroid_found,
            fnormal=fnormal,
            valid_mask=valid_mask,
        )

    def close(self) -> None:
        self._backend.close()
