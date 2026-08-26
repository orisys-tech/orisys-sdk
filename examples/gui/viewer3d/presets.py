"""Finger-compatible sensor-bundle presets for the 3D dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from orisys.finger import DEFAULT_FINGER_EXPORT_DIR


def _repo_root_candidates() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        Path.cwd(),
        here.parents[3],  # examples/gui/viewer3d -> repo root
    ]


@dataclass(frozen=True)
class SensorBundlePreset:
    label: str
    bundle_dir: str
    config: str
    export_dir: str


def _packaged_finger_preset() -> SensorBundlePreset | None:
    """Use logical names that resolve through the installed wheel sensors/ layout."""
    try:
        from orisys.configs import resolve_sensor_bundle
    except ImportError:
        return None
    bundle = resolve_sensor_bundle("finger")
    if bundle is None:
        return None
    return SensorBundlePreset(
        label="ORY-FINGER",
        bundle_dir="sensors/finger",
        config="finger",
        export_dir=DEFAULT_FINGER_EXPORT_DIR,
    )


def _load_manifest(bundle_root: Path) -> dict:
    path = bundle_root / "manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _bundle_from_root(bundle_root: Path, *, label: str | None = None) -> SensorBundlePreset | None:
    sensor_json = bundle_root / "sensor.json"
    if not sensor_json.is_file():
        return None
    manifest = _load_manifest(bundle_root)
    assets_dir = manifest.get("assets_dir", "assets/30fps-0703")
    if not isinstance(assets_dir, str) or not assets_dir.strip():
        assets_dir = "assets/30fps-0703"
    rel_bundle = bundle_root.as_posix()
    for root in _repo_root_candidates():
        try:
            rel_bundle = bundle_root.relative_to(root).as_posix()
            break
        except ValueError:
            continue
    # Packaged / checkout sensors/finger: keep resolvable product names, not absolute paths.
    if rel_bundle.replace("\\", "/").endswith("sensors/finger") or bundle_root.name == "finger":
        return SensorBundlePreset(
            label=label or "ORY-FINGER",
            bundle_dir="sensors/finger",
            config="finger",
            export_dir=DEFAULT_FINGER_EXPORT_DIR,
        )
    return SensorBundlePreset(
        label=label or "ORY-FINGER",
        bundle_dir=rel_bundle,
        config=f"{rel_bundle}/sensor.json",
        export_dir=f"{rel_bundle}/{assets_dir}".replace("\\", "/"),
    )


def default_finger_bundle() -> SensorBundlePreset:
    packaged = _packaged_finger_preset()
    if packaged is not None:
        return packaged
    for root in _repo_root_candidates():
        preset = _bundle_from_root(root / "sensors" / "finger", label="ORY-FINGER")
        if preset is not None:
            return preset
    return SensorBundlePreset(
        label="ORY-FINGER",
        bundle_dir="sensors/finger",
        config="finger",
        export_dir=DEFAULT_FINGER_EXPORT_DIR,
    )


def discover_sensor_bundle_presets() -> list[SensorBundlePreset]:
    """Return finger-compatible sensor bundle presets."""
    presets = [default_finger_bundle()]
    known_dirs = {presets[0].bundle_dir.replace("\\", "/")}

    for root in _repo_root_candidates():
        sensors_root = root / "sensors"
        if not sensors_root.is_dir():
            continue
        for child in sorted(sensors_root.iterdir()):
            if not child.is_dir():
                continue
            if child.name != "finger":
                continue
            preset = _bundle_from_root(child, label="ORY-FINGER")
            if preset is None:
                continue
            key = preset.bundle_dir.replace("\\", "/")
            if key in known_dirs:
                continue
            presets.append(preset)
            known_dirs.add(key)
        break

    return presets


def sensor_bundle_preset_index(
    config: str,
    export_dir: str,
    presets: list[SensorBundlePreset],
) -> int:
    config = (config or "").strip().replace("\\", "/")
    export_dir = (export_dir or "").strip().replace("\\", "/")
    for idx, preset in enumerate(presets):
        if config == preset.config and export_dir == preset.export_dir:
            return idx
        if config in ("finger", "dd02", "dd02-ov") and preset.config == "finger":
            return idx
        if config.endswith("/sensor.json") and export_dir.endswith("/" + Path(preset.export_dir).name):
            return idx
    return -1
