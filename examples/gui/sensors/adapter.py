"""Sensor adapters that normalize frames for Qt / multi-sensor viewers."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
import orisys

from .roi_geometry import (
    build_roi_warp,
    load_json_config,
    load_roi_polygon,
    open_video_source,
    rectified_output_size,
    warp_roi_to_rectangle,
)


NORMAL_FORCE_CAL_SLOPE = 3.92685554668795e-05
NORMAL_FORCE_CAL_OFFSET = 0.0217596967278535


@dataclass
class FrameSnapshot:
    """Normalized per-frame payload consumed by the Qt viewer."""

    image: Optional[np.ndarray] = None
    flow: Optional[np.ndarray] = None
    depth: Optional[np.ndarray] = None
    contour: Optional[np.ndarray] = None
    centroid: Any = None
    # Raw SDK force channels used for curves (same units for FN/FX/FY).
    normal_force: float = 0.0
    shear_x: float = 0.0
    shear_y: float = 0.0
    # Optional calibrated FN in Newtons for export/display overlays.
    normal_force_calibrated: float = 0.0
    fps: float = 0.0
    timestamp: float = 0.0
    raw_image: Optional[np.ndarray] = None
    processed_image: Optional[np.ndarray] = None
    flow_overlay: Optional[np.ndarray] = None
    record_frame: Optional[np.ndarray] = None


def calibrate_normal_force(raw_value: float) -> float:
    """Convert raw normal-force reading to Newtons using y = mx + c."""
    return NORMAL_FORCE_CAL_SLOPE * float(raw_value) + NORMAL_FORCE_CAL_OFFSET


class SensorAdapter(ABC):
    """Common interface between Qt and concrete sensor backends."""

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read(self) -> Optional[FrameSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


def _bgr_from_gray_or_bgr(img: np.ndarray) -> np.ndarray:
    if img is None:
        return None
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.ndim == 3 and img.shape[2] == 1:
        return cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR)
    return img


def _snapshot_from_sensor(
    sensor,
    *,
    raw_image=None,
    processed_image=None,
) -> Optional[FrameSnapshot]:
    """Build a FrameSnapshot with HHD/forces refreshed every frame."""
    if sensor is None or sensor.img is None:
        return None

    # Always decompose so FN/FX/FY update every frame (motion gating freezes forces).
    sensor.compute_deformation(decompose=True, check_motion=False)
    sensor.compute_contact()

    fps, flow, vnormal, img, contour, centroid, depth_map, fnormal, fshearx, fsheary = (
        sensor.read_info(
            sensor.info.FPS,
            sensor.info.VRAW,
            sensor.info.VNORMAL,
            sensor.info.IMG,
            sensor.info.CONTOUR,
            sensor.info.CENTROID,
            sensor.info.DEPTH,
            sensor.info.FNORMAL,
            sensor.info.FSHEARX,
            sensor.info.FSHEARY,
        )
    )

    image_bgr = _bgr_from_gray_or_bgr(img)
    processed = processed_image if processed_image is not None else image_bgr
    record = None
    if getattr(sensor, "frame", None) is not None:
        record = _bgr_from_gray_or_bgr(sensor.frame)
    elif processed is not None:
        record = processed

    flow_overlay = None
    if image_bgr is not None and flow is not None:
        flow_overlay = orisys.util.draw_arrows(
            image_bgr,
            flow,
            threshold=2,
            grid_spacing=20,
            arrow_scale=0.5,
            below_threshold_color=(160, 160, 160),
        )

    fn_raw = float(fnormal)
    return FrameSnapshot(
        image=image_bgr,
        flow=flow,
        depth=depth_map,
        contour=contour,
        centroid=centroid,
        normal_force=fn_raw,
        shear_x=float(fshearx),
        shear_y=float(fsheary),
        normal_force_calibrated=calibrate_normal_force(fn_raw),
        fps=float(fps),
        timestamp=time.time(),
        raw_image=raw_image,
        processed_image=processed,
        flow_overlay=flow_overlay,
        record_frame=record,
    )


class OrisysSensorAdapter(SensorAdapter):
    """Direct orisys.Sensor capture path (compound-eye / single-camera)."""

    def __init__(
        self,
        video,
        config_name,
        cal_path=None,
        verbose=True,
        *,
        rotate_ccw90=False,
        motion_threshold=1,
    ):
        self.video = video
        self.config_name = config_name
        self.cal_path = cal_path
        self.verbose = verbose
        self.rotate_ccw90 = bool(rotate_ccw90)
        self.motion_threshold = motion_threshold
        self.sensor = None

    def start(self) -> None:
        src = self.video
        try:
            src = int(str(src).strip())
        except (TypeError, ValueError):
            pass
        self.sensor = orisys.Sensor(
            src,
            config_name=self.config_name,
            cal_path=self.cal_path,
            verbose=self.verbose,
        )

    def read(self) -> Optional[FrameSnapshot]:
        if self.sensor is None:
            return None
        img = self.sensor.get_img()
        if img is None:
            return None

        if self.rotate_ccw90:
            self.sensor.img = cv2.rotate(self.sensor.img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            if self.sensor.frame is not None:
                self.sensor.frame = cv2.rotate(
                    self.sensor.frame, cv2.ROTATE_90_COUNTERCLOCKWISE
                )

        return _snapshot_from_sensor(
            self.sensor,
            raw_image=_bgr_from_gray_or_bgr(self.sensor.frame)
            if self.sensor.frame is not None
            else None,
            processed_image=_bgr_from_gray_or_bgr(self.sensor.img),
        )

    def reset(self) -> None:
        if self.sensor is not None:
            self.sensor.reset()

    def close(self) -> None:
        if self.sensor is not None:
            self.sensor.disconnect()
            self.sensor = None


class Dd06RoiAdapter(SensorAdapter):
    """DD06 path: external capture + polygon ROI rectify + already_processed Sensor."""

    def __init__(self, video, config_name, verbose=True, *, motion_threshold=0):
        self.video = video
        self.config_name = config_name
        self.verbose = verbose
        self.motion_threshold = motion_threshold
        self.sensor = None
        self.cap = None
        self.roi_points = None
        self.roi_image_size = None
        self.out_size = None
        self.warp_matrix = None
        self.warp_src = None
        self.last_frame_size = None
        self._source = None

    def start(self) -> None:
        config = load_json_config(self.config_name)
        self.roi_points, self.roi_image_size = load_roi_polygon(config)
        self.out_size = rectified_output_size(config, self.roi_points)
        self.sensor = orisys.Sensor(
            "external",
            config_name=self.config_name,
            verbose=self.verbose,
        )
        self.cap, self._source = open_video_source(self.video)
        self.warp_matrix = None
        self.last_frame_size = None
        if self.verbose:
            print(
                f"DD06 adapter: ROI points={len(self.roi_points)} "
                f"source_size={self.roi_image_size} output={self.out_size} "
                f"video={self._source}"
            )

    def read(self) -> Optional[FrameSnapshot]:
        if self.sensor is None or self.cap is None:
            return None

        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None

        frame_h, frame_w = frame.shape[:2]
        frame_size = (frame_w, frame_h)
        if self.warp_matrix is None or self.last_frame_size != frame_size:
            self.warp_matrix, self.warp_src, _ = build_roi_warp(
                self.roi_points,
                self.roi_image_size,
                frame_size,
                self.out_size,
            )
            self.last_frame_size = frame_size
            if self.verbose:
                print(f"Built ROI warp for frame {frame_w}x{frame_h}")

        rectified = warp_roi_to_rectangle(frame, self.warp_matrix, self.out_size)
        self.sensor.get_img(frame=rectified, already_processed=True)
        return _snapshot_from_sensor(
            self.sensor,
            raw_image=frame,
            processed_image=rectified,
        )

    def reset(self) -> None:
        if self.sensor is not None:
            self.sensor.reset()

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.sensor is not None:
            self.sensor.disconnect()
            self.sensor = None


def create_sensor_adapter(
    sensor_type: str,
    *,
    video,
    config_name,
    cal_path=None,
    verbose=True,
) -> SensorAdapter:
    """Factory for Qt / demo viewers."""
    kind = str(sensor_type or "orisys").strip().lower()
    if kind in ("orisys", "direct", "default", "compound_eye", "single_camera"):
        # Preserve historical Wuxi viewer rotation for compound-eye demos.
        rotate = kind in ("orisys", "direct", "default", "compound_eye")
        return OrisysSensorAdapter(
            video,
            config_name,
            cal_path=cal_path,
            verbose=verbose,
            rotate_ccw90=rotate,
            motion_threshold=1,
        )
    if kind in ("dd06", "dd06-ov", "roi", "polygon_roi"):
        return Dd06RoiAdapter(
            video,
            config_name,
            verbose=verbose,
            motion_threshold=0,
        )
    raise ValueError(
        f"Unknown sensor_type={sensor_type!r}; expected 'orisys' or 'dd06'"
    )
