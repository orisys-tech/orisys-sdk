"""Resolve bundled resource paths for dev runs and standalone builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_GUI_DIR = Path(__file__).resolve().parent
_EXAMPLES_DIR = _GUI_DIR.parent
_REPO_ROOT = _EXAMPLES_DIR.parent


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    """Directory containing the executable when frozen, else repository root."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _REPO_ROOT


def resource_path(*parts: str) -> Path:
    return app_root().joinpath(*parts)


def default_config_path() -> str:
    return str(resource_path("config", "dd02-ov.json"))


def configure_frozen_runtime() -> None:
    """Use the app folder as CWD so relative paths resolve next to the exe."""
    if is_frozen():
        os.chdir(app_root())


def ensure_examples_import_path() -> None:
    """Editable dev runs: keep examples/ on sys.path."""
    if is_frozen():
        return
    examples = str(_EXAMPLES_DIR)
    if examples not in sys.path:
        sys.path.insert(0, examples)
