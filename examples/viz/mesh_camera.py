"""Open3D camera helpers for finger mesh examples."""

from __future__ import annotations

from pathlib import Path

import numpy as np

DEFAULT_FINGER_VIZ_POSE = "sensors/finger/assets/visualization/world_to_cam.npy"
_LEGACY_FINGER_VIZ_POSES = {
    "assets/finger/visualization/world_to_cam.npy",
    DEFAULT_FINGER_VIZ_POSE,
}


def _finger_bundle_viz_pose_candidates() -> list[Path]:
    """Resolve viz pose paths from the packaged sensors/finger bundle when present."""
    try:
        from orisys.configs import resolve_sensor_bundle, resolve_sensor_resource
    except ImportError:
        return []

    found: list[Path] = []
    bundle = resolve_sensor_bundle("finger")
    if bundle is not None and bundle.manifest_json is not None:
        try:
            import json

            manifest = json.loads(bundle.manifest_json.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
        rel = manifest.get("viz_pose")
        if isinstance(rel, str) and rel.strip():
            found.append((bundle.root / rel).resolve())

    packaged = resolve_sensor_resource("finger", "assets", "visualization", "world_to_cam.npy")
    if packaged is not None:
        found.append(packaged.resolve())
    return found


_CAMERA_X_ROT_90 = np.array(
    [
        [1.0, 0.0, 0.0],
        [0.0, 0.0, -1.0],
        [0.0, -1.0, 0.0],
    ],
    dtype=np.float64,
)

_CAMERA_Z_ROT_180 = np.array(
    [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, -1],
        [0.0, 0.0, -1],
    ],
    dtype=np.float64,
)


def resolve_viz_pose_path(path: str | Path | None = None) -> Path:
    """Resolve world_to_cam.npy from sensor bundle, cwd, or packaged layout."""
    raw = Path(path or DEFAULT_FINGER_VIZ_POSE).expanduser()
    if raw.is_file():
        return raw.resolve()

    here = Path(__file__).resolve()
    candidates: list[Path] = []

    # Prefer the sensors/finger bundle for default / legacy relative paths.
    posix = raw.as_posix()
    if path is None or posix in _LEGACY_FINGER_VIZ_POSES or not raw.is_absolute():
        candidates.extend(_finger_bundle_viz_pose_candidates())

    try:
        from gui.app_paths import app_root

        candidates.append(app_root() / raw)
    except ImportError:
        pass
    candidates.extend(
        [
            Path.cwd() / raw,
            here.parents[2] / raw,
        ]
    )

    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique:
            unique.append(resolved)

    for candidate in unique:
        if candidate.is_file():
            return candidate

    checked = ", ".join(str(p) for p in unique)
    raise FileNotFoundError(f"Visualization pose file not found: {raw}. Checked: {checked}")


def camera_look_at_from_world_to_cam(
    world_to_cam: np.ndarray,
    *,
    lookat: np.ndarray,
    distance_scale: float = 2.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Derive Open3D look_at(center, eye, up) from a Blender world_to_cam matrix."""
    world_to_cam = np.asarray(world_to_cam, dtype=np.float64)
    cam_to_world = np.linalg.inv(world_to_cam)
    rotation = cam_to_world[:3, :3] @ _CAMERA_X_ROT_90 @ _CAMERA_Z_ROT_180

    front = rotation @ np.array([0.0, 0.0, -1.0])
    up = rotation @ np.array([0.0, 1.0, 0.0])
    front_norm = np.linalg.norm(front)
    up_norm = np.linalg.norm(up)
    if front_norm > 0:
        front = front / front_norm
    if up_norm > 0:
        up = up / up_norm

    lookat = np.asarray(lookat, dtype=np.float64).reshape(3)
    extent = float(np.linalg.norm(lookat - cam_to_world[:3, 3]))
    if extent < 1e-6:
        extent = 1.0
    eye = lookat - front * (extent * distance_scale)
    return lookat, eye, up


def default_look_at_view(
    mesh_vertices: np.ndarray,
    lookat: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fallback look_at triple when no world_to_cam pose is available."""
    center = np.asarray(lookat, dtype=np.float64).reshape(3)
    extent = np.ptp(np.asarray(mesh_vertices, dtype=np.float64), axis=0)
    span = float(np.max(extent))
    eye = center + np.array([0.0, 0.0, span * 2.0], dtype=np.float64)
    up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    return center, eye, up


def _rotation_matrix(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(axis))
    if norm < 1e-12:
        return np.eye(3, dtype=np.float64)
    axis = axis / norm
    x, y, z = axis
    cross = np.array(
        [[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]],
        dtype=np.float64,
    )
    return np.eye(3, dtype=np.float64) + np.sin(angle_rad) * cross + (1.0 - np.cos(angle_rad)) * (cross @ cross)


def orbit_eye_about_target(
    target: np.ndarray,
    eye: np.ndarray,
    up: np.ndarray,
    dx_deg: float,
    dy_deg: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Orbit ``eye`` around ``target``; dx/dy are drag deltas in degrees."""
    target = np.asarray(target, dtype=np.float64).reshape(3)
    eye = np.asarray(eye, dtype=np.float64).reshape(3)
    up = np.asarray(up, dtype=np.float64).reshape(3)

    offset = eye - target
    if float(np.linalg.norm(offset)) < 1e-9:
        offset = np.array([0.0, 0.0, 1.0], dtype=np.float64)

    world_up = up.copy()
    if float(np.linalg.norm(world_up)) < 1e-9:
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    world_up /= np.linalg.norm(world_up)

    if abs(dx_deg) > 1e-9:
        rot = _rotation_matrix(world_up, np.deg2rad(dx_deg))
        offset = rot @ offset
        up = rot @ up

    forward = -offset
    forward_norm = float(np.linalg.norm(forward))
    if forward_norm > 1e-9:
        forward = forward / forward_norm
        right = np.cross(forward, up)
        right_norm = float(np.linalg.norm(right))
        if right_norm > 1e-9:
            right = right / right_norm
            if abs(dy_deg) > 1e-9:
                rot = _rotation_matrix(right, np.deg2rad(dy_deg))
                offset = rot @ offset
                up = rot @ up

    new_eye = target + offset
    up_norm = float(np.linalg.norm(up))
    if up_norm > 1e-9:
        up = up / up_norm
    return new_eye, up


def apply_view_from_world_to_cam(vis, world_to_cam: np.ndarray, *, lookat: np.ndarray) -> None:
    """Apply Blender-exported world_to_cam as the Open3D default view."""
    world_to_cam = np.asarray(world_to_cam, dtype=np.float64)
    cam_to_world = np.linalg.inv(world_to_cam)
    rotation = cam_to_world[:3, :3] @ _CAMERA_X_ROT_90 @ _CAMERA_Z_ROT_180

    front = rotation @ np.array([0.0, 0.0, -1.0])
    up = rotation @ np.array([0.0, 1.0, 0.0])
    front_norm = np.linalg.norm(front)
    up_norm = np.linalg.norm(up)
    if front_norm > 0:
        front = front / front_norm
    if up_norm > 0:
        up = up / up_norm

    view_control = vis.get_view_control()
    view_control.set_lookat(lookat.astype(np.float64))
    view_control.set_front(front.astype(np.float64))
    view_control.set_up(up.astype(np.float64))
    vis.update_renderer()


def apply_mesh_lighting(vis) -> None:
    """Enable shaded lighting on the legacy Open3D Visualizer."""
    import open3d as o3d

    render_option = vis.get_render_option()
    if hasattr(render_option, "light_on"):
        render_option.light_on = True
    if hasattr(render_option, "mesh_color_option"):
        render_option.mesh_color_option = o3d.visualization.MeshColorOption.Color
    if hasattr(render_option, "mesh_shade_option"):
        render_option.mesh_shade_option = o3d.visualization.MeshShadeOption.Color
    vis.update_renderer()


def normalize_light_direction(direction) -> np.ndarray:
    d = np.asarray(direction, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(d))
    if norm <= 0:
        return np.array([0.0, 0.0, -1.0], dtype=np.float64)
    return d / norm


def apply_filament_sun_light(renderer, *, direction, intensity: float) -> None:
    """Configure Filament sun light on an OffscreenRenderer."""
    scene = renderer.scene
    if not hasattr(scene, "scene"):
        return
    filament = scene.scene
    sun_dir = normalize_light_direction(direction).tolist()
    if hasattr(filament, "set_sun_light"):
        filament.set_sun_light(sun_dir, [1.0, 1.0, 1.0], float(intensity))
    if hasattr(filament, "enable_sun_light"):
        filament.enable_sun_light(True)


def compute_vertex_normals(vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Per-vertex normals for a triangle mesh (vectorized)."""
    vertices = np.asarray(vertices, dtype=np.float64)
    triangles = np.asarray(triangles, dtype=np.int32)
    v0 = vertices[triangles[:, 0]]
    v1 = vertices[triangles[:, 1]]
    v2 = vertices[triangles[:, 2]]
    face_normals = np.cross(v1 - v0, v2 - v0)
    normals = np.zeros_like(vertices)
    np.add.at(normals, triangles[:, 0], face_normals)
    np.add.at(normals, triangles[:, 1], face_normals)
    np.add.at(normals, triangles[:, 2], face_normals)
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-12
    normals[valid] /= lengths[valid, np.newaxis]
    normals[~valid] = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    return normals


def precompute_shade_factors(vertices: np.ndarray, triangles: np.ndarray, lighting) -> np.ndarray:
    """Per-vertex shade multipliers from static mesh geometry and layout lighting."""
    normals = compute_vertex_normals(vertices, triangles)
    d = normalize_light_direction(lighting.direction)
    ndotl = np.clip(normals @ d, 0.0, 1.0)
    return float(lighting.ambient) + float(lighting.diffuse) * ndotl


def apply_shade_factors(colors: np.ndarray, shade_factors: np.ndarray | None) -> np.ndarray:
    if shade_factors is None:
        return colors
    return np.clip(np.asarray(colors, dtype=np.float64) * shade_factors[:, np.newaxis], 0.0, 1.0)


def shade_vertex_colors(
    colors: np.ndarray,
    normals: np.ndarray,
    *,
    direction,
    ambient: float,
    diffuse: float,
) -> np.ndarray:
    """Apply directional shading to vertex colors (legacy viewer path)."""
    colors = np.asarray(colors, dtype=np.float64)
    normals = np.asarray(normals, dtype=np.float64)
    d = normalize_light_direction(direction)
    ndotl = np.clip(normals @ d, 0.0, 1.0)
    shade = float(ambient) + float(diffuse) * ndotl
    return np.clip(colors * shade[:, np.newaxis], 0.0, 1.0)
