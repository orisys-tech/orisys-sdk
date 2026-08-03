"""Display snapshot produced by one finger pipeline tick."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class FingerFrameView:
    timestamp: float
    fps: float
    unrolled: np.ndarray
    flow: np.ndarray
    vnormal: np.ndarray
    depth_map: np.ndarray
    img: np.ndarray
    contour: np.ndarray
    centroid: np.ndarray
    fnormal: float
    fshearx: float
    fsheary: float
    centroid_found: bool
    mask_coverage: float
    valid_mask: np.ndarray | None = None
    raw_frame: np.ndarray | None = None

    @classmethod
    def from_tactile(cls, tactile, unrolled, *, timestamp: float) -> FingerFrameView:
        """Build a display snapshot from tactile state (mask + fields assembled here)."""
        fps, flow, vnormal, depth_map, centroid, fnormal, fshearx, fsheary = tactile.read_info(
            tactile.info.FPS,
            tactile.info.VRAW,
            tactile.info.VNORMAL,
            tactile.info.DEPTH,
            tactile.info.CENTROID,
            tactile.info.FNORMAL,
            tactile.info.FSHEARX,
            tactile.info.FSHEARY,
        )
        mask = tactile.valid_mask
        return cls(
            timestamp=timestamp,
            fps=float(fps),
            unrolled=unrolled,
            flow=flow,
            vnormal=vnormal,
            depth_map=depth_map,
            img=np.array([]),
            contour=np.array([]),
            centroid=centroid,
            fnormal=float(fnormal),
            fshearx=float(fshearx),
            fsheary=float(fsheary),
            centroid_found=bool(tactile.raw_sensor.centroid_found),
            mask_coverage=float(tactile.mask_stats["coverage"]),
            valid_mask=mask.copy() if mask is not None else None,
            raw_frame=tactile.frame,
        )
