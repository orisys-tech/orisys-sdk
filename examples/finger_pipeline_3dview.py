#!/usr/bin/env python3
"""
ORY-FINGER：UV-unroll finger tactile pipeline with unified Qt dashboard.

Where to customize the GUI:
  Layout (sizes, proportions)  ->  examples/gui/viewer3d/layout.py
  Colors / QSS                 ->  examples/gui/viewer3d/styles.py
  Widget rendering logic       ->  examples/gui/viewer3d/widgets/
  Window behavior              ->  examples/gui/viewer3d/dashboard.py

Recommended entry:
  python examples/finger_pipeline_3dview.py --video 0 --config finger
"""

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

# Make shared packages importable when launched as a file path.
_EXAMPLES_DIR = Path(__file__).resolve().parent
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from gui.app_paths import (
    configure_frozen_runtime,
    default_config_path,
    ensure_examples_import_path,
    require_gui_extras,
)

configure_frozen_runtime()
ensure_examples_import_path()
require_gui_extras()

from gui import run_dashboard
from pipeline import PipelineConfig
from viz import DEFAULT_FINGER_VIZ_POSE


def _parse_args():
    parser = argparse.ArgumentParser(
        description="UV-unroll finger tactile pipeline with unified Qt dashboard"
    )
    parser.add_argument("--video", "-v", default="0", help="Camera index or video file path")
    parser.add_argument("--config", "-c", default=default_config_path(), help="Orisys SDK config")
    parser.add_argument("--cal", default="", help="Optional calibration file path")
    parser.add_argument("--verbose", action="store_true", help="SDK verbose logs")
    parser.add_argument(
        "--mesh-map",
        choices=["flow", "depth"],
        default="depth",
        help="Color the 3D mesh from flow magnitude or contact depth.",
    )
    parser.add_argument("--threshold", type=float, default=None, help="Mesh/arrow threshold")
    parser.add_argument("--no-3d", action="store_true", help="Disable 3D mesh view")
    parser.add_argument(
        "--viz-pose",
        default=DEFAULT_FINGER_VIZ_POSE,
        help="world_to_cam.npy for the default view; pass 'none' to skip",
    )
    parser.add_argument(
        "--cutoff",
        type=float,
        default=5.0,
        help="Low-pass cutoff for force curves (Hz)",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Print per-stage timing to the log panel / console",
    )
    parser.add_argument(
        "--profile-every",
        type=int,
        default=30,
        help="When --profile is set, print rolling averages every N frames",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    config = PipelineConfig.from_args(args)
    sys.exit(run_dashboard(config))


if __name__ == "__main__":
    main()
