"""Contact normal-force arrow overlay for finger 3D mesh examples."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from orisys.finger.mesh import UVSurfaceMesh, compute_uv_surface_frames

ForceStrengthMode = Literal["log", "power", "linear"]


@dataclass(frozen=True)
class ContactArrowStyle:
    """Visual tuning for the 3D contact normal arrow (dashboard: edit MESH_CONTACT_ARROW in layout.py)."""

    normal_force_scale: float = 1.0
    min_length_fraction: float = 0.02
    max_length_fraction: float = 0.30
    min_thickness_scale: float = 0.20
    max_thickness_scale: float = 1.0
    reference_normal_force: float = 10000.0
    force_strength_mode: ForceStrengthMode = "log"
    force_strength_gamma: float = 0.5
    color: tuple[float, float, float] = (1.0, 0.92, 0.10)


DEFAULT_CONTACT_ARROW_STYLE = ContactArrowStyle()

# Backward-compatible aliases (match DEFAULT_CONTACT_ARROW_STYLE).
DEFAULT_NORMAL_FORCE_SCALE = DEFAULT_CONTACT_ARROW_STYLE.normal_force_scale
MIN_ARROW_LENGTH_FRACTION = DEFAULT_CONTACT_ARROW_STYLE.min_length_fraction
MAX_ARROW_LENGTH_FRACTION = DEFAULT_CONTACT_ARROW_STYLE.max_length_fraction
MIN_ARROW_THICKNESS_SCALE = DEFAULT_CONTACT_ARROW_STYLE.min_thickness_scale
MAX_ARROW_THICKNESS_SCALE = DEFAULT_CONTACT_ARROW_STYLE.max_thickness_scale
REFERENCE_NORMAL_FORCE = DEFAULT_CONTACT_ARROW_STYLE.reference_normal_force
FORCE_STRENGTH_MODE = DEFAULT_CONTACT_ARROW_STYLE.force_strength_mode
FORCE_STRENGTH_GAMMA = DEFAULT_CONTACT_ARROW_STYLE.force_strength_gamma
CONTACT_ARROW_COLOR = DEFAULT_CONTACT_ARROW_STYLE.color


def force_visual_strength(
    force: float,
    *,
    style: ContactArrowStyle = DEFAULT_CONTACT_ARROW_STYLE,
) -> float:
    """Map normal force Fn to a unitless strength in [0, 1] for length and thickness."""
    reference = style.reference_normal_force
    if force <= 0.0 or reference <= 0.0:
        return 0.0

    ratio = force / reference
    mode = style.force_strength_mode

    if mode == "linear":
        strength = ratio
    elif mode == "power":
        strength = ratio ** style.force_strength_gamma
    else:  # log
        strength = np.log1p(ratio) / np.log1p(1.0)

    return float(np.clip(strength, 0.0, 1.0))


def thickness_scale_from_force(
    force: float,
    *,
    style: ContactArrowStyle = DEFAULT_CONTACT_ARROW_STYLE,
) -> float:
    """Radial scale from Fn using the shared force_strength curve."""
    strength = force_visual_strength(force, style=style)
    span = style.max_thickness_scale - style.min_thickness_scale
    return float(style.min_thickness_scale + span * strength)


def length_from_force(
    force: float,
    mesh_span: float,
    *,
    style: ContactArrowStyle = DEFAULT_CONTACT_ARROW_STYLE,
) -> float:
    """Arrow length in world units from Fn and mesh extent."""
    strength = force_visual_strength(force, style=style)
    frac_span = style.max_length_fraction - style.min_length_fraction
    fraction = style.min_length_fraction + frac_span * strength
    return float(mesh_span * fraction * style.normal_force_scale)


def _mesh_span(vertices: np.ndarray) -> float:
    extent = np.ptp(vertices, axis=0)
    return float(max(np.max(extent), 1e-6))


def _rotation_matrix_z_to(direction: np.ndarray) -> np.ndarray:
    """Rotation matrix mapping unit +Z to ``direction``."""
    direction = np.asarray(direction, dtype=np.float64).reshape(3)
    norm = np.linalg.norm(direction)
    if norm < 1e-8:
        return np.eye(3, dtype=np.float64)
    direction = direction / norm

    z_axis = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    cross = np.cross(z_axis, direction)
    dot = float(np.dot(z_axis, direction))
    if dot > 0.9999:
        return np.eye(3, dtype=np.float64)
    if dot < -0.9999:
        return np.diag([1.0, -1.0, -1.0]).astype(np.float64)

    skew = np.array(
        [
            [0.0, -cross[2], cross[1]],
            [cross[2], 0.0, -cross[0]],
            [-cross[1], cross[0], 0.0],
        ],
        dtype=np.float64,
    )
    return np.eye(3, dtype=np.float64) + skew + skew @ skew * (1.0 / (1.0 + dot))


def _scale_arrow_template(
    template_vertices: np.ndarray,
    *,
    length_scale: float,
    thickness_scale: float,
) -> np.ndarray:
    """Scale a +Z arrow template axially and radially."""
    scaled = np.asarray(template_vertices, dtype=np.float64).copy()
    scaled[:, 0] *= thickness_scale
    scaled[:, 1] *= thickness_scale
    scaled[:, 2] *= length_scale
    return scaled


def create_arrow_template(o3d):
    """Unit-height arrow mesh along +Z; radial size is scaled per-frame from force."""
    arrow = o3d.geometry.TriangleMesh.create_arrow(
        cylinder_radius=0.15,
        cone_radius=0.3,
        cylinder_height=0.72,
        cone_height=0.28,
    )
    arrow.compute_vertex_normals()
    return (
        np.asarray(arrow.vertices, dtype=np.float64),
        np.asarray(arrow.triangles, dtype=np.int32),
    )


def build_contact_normal_arrow_mesh(
    origin: np.ndarray,
    normal: np.ndarray,
    length: float,
    force: float,
    *,
    mesh_span: float,
    template_vertices: np.ndarray,
    template_triangles: np.ndarray,
    style: ContactArrowStyle = DEFAULT_CONTACT_ARROW_STYLE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a 3D arrow mesh pointing opposite the surface normal."""
    origin = np.asarray(origin, dtype=np.float64).reshape(3)
    normal = np.asarray(normal, dtype=np.float64).reshape(3)
    norm = np.linalg.norm(normal)
    color = np.tile(np.asarray(style.color, dtype=np.float64), (len(template_vertices), 1))

    radial_scale = thickness_scale_from_force(force, style=style)
    if norm < 1e-8 or length <= 0.0 or radial_scale <= 0.0 or not np.all(np.isfinite(origin)):
        return np.zeros_like(template_vertices), template_triangles, color

    direction = -normal / norm
    length = float(
        np.clip(
            length,
            mesh_span * style.min_length_fraction,
            mesh_span * style.max_length_fraction,
        )
    )
    if length <= 0.0:
        return np.zeros_like(template_vertices), template_triangles, color

    rotation = _rotation_matrix_z_to(direction)
    scaled_template = _scale_arrow_template(
        template_vertices,
        length_scale=length,
        thickness_scale=radial_scale,
    )
    vertices = scaled_template @ rotation.T + origin
    return vertices, template_triangles, color


def create_arrow_mesh_geometry(
    o3d,
    template_vertices: np.ndarray,
    template_triangles: np.ndarray,
    *,
    style: ContactArrowStyle = DEFAULT_CONTACT_ARROW_STYLE,
):
    """Create a persistent Open3D mesh for the contact arrow overlay."""
    arrow_mesh = o3d.geometry.TriangleMesh()
    arrow_mesh.vertices = o3d.utility.Vector3dVector(np.zeros_like(template_vertices))
    arrow_mesh.triangles = o3d.utility.Vector3iVector(template_triangles)
    arrow_mesh.vertex_colors = o3d.utility.Vector3dVector(
        np.tile(np.asarray(style.color, dtype=np.float64), (len(template_vertices), 1))
    )
    arrow_mesh.compute_vertex_normals()
    return arrow_mesh


class ContactArrowOverlay:
    """Example-layer contact arrow driven by centroid and normal force."""

    def __init__(
        self,
        mesh: UVSurfaceMesh,
        *,
        style: ContactArrowStyle | None = None,
        normal_force_scale: float | None = None,
        enabled: bool = True,
    ):
        import open3d as o3d

        self.mesh = mesh
        base_style = style or DEFAULT_CONTACT_ARROW_STYLE
        if normal_force_scale is not None:
            base_style = replace(base_style, normal_force_scale=float(normal_force_scale))
        self.style = base_style
        self.enabled = enabled
        self._mesh_span = _mesh_span(mesh.rest_vertices)
        _, _, self._surface_normals = compute_uv_surface_frames(mesh.world_xyz, mesh.valid_mask)
        self._template_vertices, self._template_triangles = (
            create_arrow_template(o3d) if enabled else (None, None)
        )
        self.arrow_mesh = (
            create_arrow_mesh_geometry(
                o3d,
                self._template_vertices,
                self._template_triangles,
                style=self.style,
            )
            if enabled
            else None
        )

    @property
    def normal_force_scale(self) -> float:
        return self.style.normal_force_scale

    def compute(
        self,
        centroid,
        centroid_found: bool,
        fnormal: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        if not self.enabled or self.arrow_mesh is None:
            return None

        style = self.style
        template_vertices = self._template_vertices
        template_triangles = self._template_triangles
        color = np.tile(np.asarray(style.color, dtype=np.float64), (len(template_vertices), 1))
        hidden = (np.zeros_like(template_vertices), template_triangles, color)

        if not centroid_found or centroid is None:
            return hidden

        centroid = np.asarray(centroid, dtype=np.float64).reshape(-1)
        if centroid.size < 2:
            return hidden

        cx, cy = int(round(centroid[0])), int(round(centroid[1]))
        h, w = self.mesh.shape
        if not (0 <= cy < h and 0 <= cx < w):
            return hidden
        if self.mesh.index_map[cy, cx] < 0:
            return hidden

        origin = self.mesh.world_xyz[cy, cx]
        normal = self._surface_normals[cy, cx]
        if not np.all(np.isfinite(origin)) or not np.all(np.isfinite(normal)):
            return hidden

        force = max(float(fnormal), 0.0)
        if force <= 0.0:
            return hidden

        length = length_from_force(force, self._mesh_span, style=style)
        return build_contact_normal_arrow_mesh(
            origin,
            normal,
            length,
            force,
            mesh_span=self._mesh_span,
            template_vertices=template_vertices,
            template_triangles=template_triangles,
            style=style,
        )

    def apply(self, arrow_vertices: np.ndarray, arrow_colors: np.ndarray) -> None:
        import open3d as o3d

        self.arrow_mesh.vertices = o3d.utility.Vector3dVector(arrow_vertices.astype(np.float64))
        self.arrow_mesh.vertex_colors = o3d.utility.Vector3dVector(arrow_colors.astype(np.float64))
        self.arrow_mesh.compute_vertex_normals()
