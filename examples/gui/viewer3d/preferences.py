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


def preference_path() -> Path:
    # Keep preference file at examples/gui/preference.json
    return _GUI_DIR / PREFERENCE_FILE


def legacy_camera_selection_path() -> Path:
    return resource_path(LEGACY_CAMERA_SELECTION_FILE)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_preferences() -> dict[str, Any]:
    """Load preferences, migrating camera_id from legacy file when needed."""
    prefs = _read_json(preference_path())
    if "video_source" not in prefs:
        legacy = _read_json(legacy_camera_selection_path())
        camera_id = legacy.get("camera_id")
        if camera_id is not None and str(camera_id).strip():
            prefs["video_source"] = str(camera_id).strip()
    return prefs


def save_preferences(prefs: dict[str, Any]) -> None:
    """Write preferences atomically enough for dashboard use."""
    if not isinstance(prefs, dict):
        return
    path = preference_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prefs, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def get_preferred_video_source(prefs: dict[str, Any] | None = None) -> str | None:
    data = prefs if prefs is not None else load_preferences()
    value = data.get("video_source")
    if value is None:
        return None
    text = str(value).strip()
    return text or None
