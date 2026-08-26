"""Load/save dashboard user preferences for the finger 3D viewer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gui.app_paths import resource_path

PREFERENCE_FILE = "preference.json"
LEGACY_CAMERA_SELECTION_FILE = "camera_selection.json"
# Keep preference.json at examples/gui/ for backward compatibility.
_GUI_DIR = Path(__file__).resolve().parents[1]

# Old lab / repo-relative paths that predate packaged sensors/<name>/.
_LEGACY_CONFIG_PATHS = {
    "dd02",
    "dd02-ov",
    "config/dd02-ov.json",
    "./config/dd02-ov.json",
    "config/finger.json",
    "./config/finger.json",
    "sensors/finger/sensor.json",
}


def preference_path() -> Path:
    # Keep preference file at examples/gui/preference.json
    return _GUI_DIR / PREFERENCE_FILE


def legacy_camera_selection_path() -> Path:
    return resource_path(LEGACY_CAMERA_SELECTION_FILE)


def default_finger_config() -> str:
    """Public product config stem resolved via packaged ``sensors/finger``."""
    return "finger"


def default_finger_assets_dir() -> str:
    try:
        from orisys.finger import DEFAULT_FINGER_EXPORT_DIR

        return DEFAULT_FINGER_EXPORT_DIR
    except ImportError:
        return "sensors/finger/assets/30fps-0703"


def packaged_finger_bundle_root() -> Path | None:
    """Filesystem root of the installed ``sensors/finger`` bundle when present."""
    try:
        from orisys.configs import resolve_sensor_bundle
    except ImportError:
        return None
    bundle = resolve_sensor_bundle("finger")
    return bundle.root if bundle is not None else None


def packaged_finger_assets_root() -> Path | None:
    try:
        from orisys.configs import resolve_sensor_asset_dir
    except ImportError:
        return None
    return resolve_sensor_asset_dir("finger")


def normalize_config_preference(value: str | None) -> str:
    """Map legacy config paths to the packaged ``finger`` sensor name."""
    if value is None or not str(value).strip():
        return default_finger_config()
    text = str(value).strip().replace("\\", "/")
    if text in _LEGACY_CONFIG_PATHS or text.endswith("/dd02-ov.json"):
        return default_finger_config()

    root = packaged_finger_bundle_root()
    if root is not None:
        try:
            if Path(value).resolve() == (root / "sensor.json").resolve():
                return default_finger_config()
        except OSError:
            pass
    return text


def normalize_assets_preference(value: str | None) -> str:
    """Prefer packaged ``sensors/finger/assets/...`` when saved paths are stale."""
    default = default_finger_assets_dir()
    if value is None or not str(value).strip():
        return default
    text = str(value).strip()
    posix = text.replace("\\", "/")
    if posix == default or posix.endswith("/sensors/finger/assets/30fps-0703"):
        return default

    path = Path(text)
    if path.is_dir():
        packaged = packaged_finger_assets_root()
        if packaged is not None:
            try:
                if path.resolve() == packaged.resolve():
                    return default
            except OSError:
                pass
        # Keep a user-selected custom directory that still exists.
        if "sensors/finger" in posix or path.name == "30fps-0703":
            return text if path.is_absolute() else default
        return text

    # Missing old absolute/repo paths (assets/finger, ./config era) -> packaged default.
    return default


def _normalize_preferences(prefs: dict[str, Any]) -> dict[str, Any]:
    prefs = dict(prefs)
    if "config_path" in prefs or prefs:
        prefs["config_path"] = normalize_config_preference(prefs.get("config_path"))
    if "finger_assets_dir" in prefs or prefs:
        prefs["finger_assets_dir"] = normalize_assets_preference(prefs.get("finger_assets_dir"))
    prefs.setdefault("sensor_bundle_dir", "sensors/finger")
    return prefs


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_preferences() -> dict[str, Any]:
    """Load preferences, migrating camera_id / legacy config paths when needed."""
    prefs = _read_json(preference_path())
    if "video_source" not in prefs:
        legacy = _read_json(legacy_camera_selection_path())
        camera_id = legacy.get("camera_id")
        if camera_id is not None and str(camera_id).strip():
            prefs["video_source"] = str(camera_id).strip()
    return _normalize_preferences(prefs)


def save_preferences(prefs: dict[str, Any]) -> None:
    """Write preferences atomically enough for dashboard use."""
    if not isinstance(prefs, dict):
        return
    path = preference_path()
    normalized = _normalize_preferences(prefs)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def get_preferred_video_source(prefs: dict[str, Any] | None = None) -> str | None:
    data = prefs if prefs is not None else load_preferences()
    value = data.get("video_source")
    if value is None:
        return None
    text = str(value).strip()
    return text or None
