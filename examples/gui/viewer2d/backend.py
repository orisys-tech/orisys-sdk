"""Qt-facing display backend for sensor viewer snapshots.

Separates acquisition (`gui.sensors.FrameSnapshot`) from Qt display state:
normalized images, force history / filtering, and aspect-ratio metadata.
Does not import camera, ROI, or `orisys.Sensor`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Sequence, Tuple

import cv2
import numpy as np
import orisys
from scipy.signal import butter, filtfilt

FORCE_SAMPLE_RATE_HZ = 30.0
PLOT_BUFFER_POINTS = 120
PLOT_WINDOW_SEC = PLOT_BUFFER_POINTS / FORCE_SAMPLE_RATE_HZ
Y_AXIS_MIN_SPAN = 20000.0

ArrowBackground = Literal["pure_color", "captured"]
# #0B1016 as BGR (matches demo_wuxi / promote_video theme)
PURE_COLOR_BG_BGR = (22, 16, 11)

_ARROW_DRAW_KW = dict(
    threshold=2,
    grid_spacing=20,
    arrow_scale=0.5,
    below_threshold_color=(160, 160, 160),
)


@dataclass
class ViewerFrame:
    """Normalized display payload for one UI tick."""

    display_image: np.ndarray
    image_height: int
    image_width: int
    aspect_ratio: float  # width / height
    depth: Optional[np.ndarray]
    normal_force: float
    shear_x: float
    shear_y: float
    normal_force_calibrated: float
    fps: float
    timestamp: float
    record_frame: Optional[np.ndarray]


@dataclass
class ForcePlotState:
    """Filtered force series ready for pyqtgraph curves."""

    times: np.ndarray  # shape (n,)
    values: np.ndarray  # shape (n, 3)  FN, FX, FY
    sample_count: int
    x_range: Tuple[float, float]
    y_ranges: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]


def lowpass_filter(
    data,
    cutoff_hz: float,
    sample_rate_hz: float = FORCE_SAMPLE_RATE_HZ,
    order: int = 2,
) -> np.ndarray:
    """Zero-phase Butterworth low-pass for uniformly sampled 1-D data."""
    y = np.asarray(data, dtype=np.float64)
    if cutoff_hz == 0:
        return y.copy()
    if y.size == 0:
        return y

    nyquist = 0.5 * sample_rate_hz
    if cutoff_hz < 0 or cutoff_hz >= nyquist:
        raise ValueError(
            f"cutoff_hz must be in (0, {nyquist}) for sample_rate_hz={sample_rate_hz}"
        )

    b, a = butter(order, cutoff_hz / nyquist, btype="low")
    padlen = 3 * (max(len(b), len(a)) - 1)
    if y.size <= padlen:
        return y.copy()
    return filtfilt(b, a, y)


def ensure_bgr(img: Optional[np.ndarray]) -> Optional[np.ndarray]:
    if img is None:
        return None
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.ndim == 3 and img.shape[2] == 1:
        return cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR)
    return img


def image_shape_meta(img: np.ndarray) -> Tuple[int, int, float]:
    """Return (height, width, width/height) from a display image."""
    h, w = int(img.shape[0]), int(img.shape[1])
    aspect = float(w) / float(h) if h > 0 else 1.0
    return h, w, aspect


def _base_bgr(snapshot) -> Optional[np.ndarray]:
    for attr in ("image", "processed_image", "raw_image"):
        out = ensure_bgr(getattr(snapshot, attr, None))
        if out is not None:
            return out
    return None


def select_display_image(snapshot) -> np.ndarray:
    """Pick flow overlay / processed / raw image for the left panel."""
    arrows = getattr(snapshot, "flow_overlay", None)
    if arrows is not None:
        out = ensure_bgr(arrows)
        if out is not None:
            return out

    for attr in ("processed_image", "image", "raw_image"):
        base = getattr(snapshot, attr, None)
        out = ensure_bgr(base)
        if out is not None:
            return out

    return np.zeros((400, 400, 3), dtype=np.uint8)


def build_display_image(
    snapshot,
    background: ArrowBackground = "pure_color",
) -> np.ndarray:
    """Build left-panel image: arrows on pure color or on the captured frame."""
    flow = getattr(snapshot, "flow", None)
    base = _base_bgr(snapshot)

    if flow is not None and base is not None:
        if background == "pure_color":
            h, w = base.shape[:2]
            canvas = np.empty((h, w, 3), dtype=np.uint8)
            canvas[:, :] = PURE_COLOR_BG_BGR
            return orisys.util.draw_arrows(canvas, flow, **_ARROW_DRAW_KW)

        overlay = ensure_bgr(getattr(snapshot, "flow_overlay", None))
        if overlay is not None:
            return overlay
        return orisys.util.draw_arrows(base, flow, **_ARROW_DRAW_KW)

    return select_display_image(snapshot)


def bgr_to_rgb_bytes(img_bgr: np.ndarray) -> Tuple[np.ndarray, int, int]:
    """Convert BGR uint8 image to contiguous RGB for QImage."""
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    if not rgb.flags["C_CONTIGUOUS"]:
        rgb = np.ascontiguousarray(rgb)
    h, w = rgb.shape[:2]
    return rgb, h, w


def scale_bgr_to_fit(
    img_bgr: np.ndarray,
    max_w: int,
    max_h: int,
) -> np.ndarray:
    """Resize preserving aspect ratio to fit inside (max_w, max_h)."""
    if max_w <= 0 or max_h <= 0:
        return img_bgr
    h, w = img_bgr.shape[:2]
    if h <= 0 or w <= 0:
        return img_bgr
    scale = min(max_w / float(w), max_h / float(h))
    if abs(scale - 1.0) < 1e-6:
        return img_bgr
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)


def panel_width_for_aspect(
    available_height: int,
    aspect_ratio: float,
    *,
    min_size: int = 160,
) -> int:
    """Preferred left-panel width given available height and image aspect."""
    h = max(int(available_height), min_size)
    w = int(round(h * float(aspect_ratio)))
    return max(w, min_size)


class ForceHistory:
    """Ring-style force history buffer with filtering and y-range smoothing."""

    def __init__(
        self,
        npoints: int = PLOT_BUFFER_POINTS,
        *,
        sample_rate_hz: float = FORCE_SAMPLE_RATE_HZ,
        lowpass_cutoff_hz: float = 10.0,
        y_axis_min_span: float = Y_AXIS_MIN_SPAN,
        y_range_alpha: float = 0.5,
    ):
        self.npoints = int(npoints)
        self.sample_rate_hz = float(sample_rate_hz)
        self.lowpass_cutoff_hz = float(lowpass_cutoff_hz)
        self.y_axis_min_span = float(y_axis_min_span)
        self.y_range_alpha = float(y_range_alpha)
        self.window_sec = self.npoints / self.sample_rate_hz
        self.reset()

    def reset(self) -> None:
        self.data = np.full((self.npoints, 2, 3), np.nan, dtype=np.float64)
        self.sample_count = 0
        self._y_range_smooth = [None, None, None]

    def push(self, t: float, fn: float, fx: float, fy: float) -> None:
        values = (float(fn), float(fx), float(fy))
        if self.sample_count < self.npoints:
            idx = self.sample_count
            self.data[idx, 0, :] = t
            self.data[idx, 1, :] = values
            self.sample_count += 1
            return

        self.data[:-1, 0, :] = self.data[1:, 0, :]
        self.data[:-1, 1, :] = self.data[1:, 1, :]
        self.data[-1, 0, :] = t
        self.data[-1, 1, :] = values

    def _smooth_y_range(self, channel: int, ymin: float, ymax: float) -> Tuple[float, float]:
        if self._y_range_smooth[channel] is None:
            smoothed = (ymin, ymax)
        else:
            prev_min, prev_max = self._y_range_smooth[channel]
            alpha = self.y_range_alpha
            ymin = alpha * ymin + (1.0 - alpha) * prev_min
            ymax = alpha * ymax + (1.0 - alpha) * prev_max
            smoothed = (ymin, ymax)

        span = smoothed[1] - smoothed[0]
        if span < self.y_axis_min_span:
            mid = 0.5 * (smoothed[0] + smoothed[1])
            half = self.y_axis_min_span / 2.0
            smoothed = (mid - half, mid + half)

        self._y_range_smooth[channel] = smoothed
        pad = max((smoothed[1] - smoothed[0]) * 0.12, 0.01)
        return smoothed[0] - pad, smoothed[1] + pad

    def plot_state(self) -> Optional[ForcePlotState]:
        n = self.sample_count
        if n == 0:
            return None

        data_plot = self.data[:n].copy()
        for i in range(3):
            data_plot[:, 1, i] = lowpass_filter(
                data_plot[:, 1, i],
                self.lowpass_cutoff_hz,
                sample_rate_hz=self.sample_rate_hz,
            )

        times = data_plot[:, 0, 0].copy()
        values = data_plot[:, 1, :].copy()
        y_ranges = tuple(
            self._smooth_y_range(i, float(values[:, i].min()), float(values[:, i].max()))
            for i in range(3)
        )

        if n < self.npoints:
            x_range = (0.0, self.window_sec)
        else:
            x0 = float(times[0])
            x1 = float(times[-1])
            if x1 <= x0:
                x1 = x0 + self.window_sec
            x_range = (x0, x1)

        return ForcePlotState(
            times=times,
            values=values,
            sample_count=n,
            x_range=x_range,
            y_ranges=y_ranges,  # type: ignore[arg-type]
        )


class QtViewerBackend:
    """Normalize FrameSnapshot into display images + force history."""

    def __init__(
        self,
        *,
        npoints: int = PLOT_BUFFER_POINTS,
        lowpass_cutoff_hz: float = 10.0,
        y_axis_min_span: float = Y_AXIS_MIN_SPAN,
        arrow_background: ArrowBackground = "pure_color",
    ):
        self.force_history = ForceHistory(
            npoints=npoints,
            lowpass_cutoff_hz=lowpass_cutoff_hz,
            y_axis_min_span=y_axis_min_span,
        )
        self._start_time: Optional[float] = None
        self.last_viewer_frame: Optional[ViewerFrame] = None
        self.arrow_background: ArrowBackground = arrow_background

    def set_arrow_background(self, background: ArrowBackground) -> None:
        self.arrow_background = background

    def rebuild_display(self, snapshot) -> ViewerFrame:
        """Re-render display image without advancing force history."""
        display = build_display_image(snapshot, self.arrow_background)
        h, w, aspect = image_shape_meta(display)
        prev = self.last_viewer_frame
        if prev is not None:
            frame = ViewerFrame(
                display_image=display,
                image_height=h,
                image_width=w,
                aspect_ratio=aspect,
                depth=prev.depth,
                normal_force=prev.normal_force,
                shear_x=prev.shear_x,
                shear_y=prev.shear_y,
                normal_force_calibrated=prev.normal_force_calibrated,
                fps=prev.fps,
                timestamp=prev.timestamp,
                record_frame=prev.record_frame,
            )
        else:
            frame = ViewerFrame(
                display_image=display,
                image_height=h,
                image_width=w,
                aspect_ratio=aspect,
                depth=getattr(snapshot, "depth", None),
                normal_force=float(getattr(snapshot, "normal_force", 0.0)),
                shear_x=float(getattr(snapshot, "shear_x", 0.0)),
                shear_y=float(getattr(snapshot, "shear_y", 0.0)),
                normal_force_calibrated=float(
                    getattr(snapshot, "normal_force_calibrated", 0.0)
                ),
                fps=float(getattr(snapshot, "fps", 0.0)),
                timestamp=float(getattr(snapshot, "timestamp", 0.0) or 0.0),
                record_frame=ensure_bgr(getattr(snapshot, "record_frame", None)),
            )
        self.last_viewer_frame = frame
        return frame

    def reset(self) -> None:
        self.force_history.reset()
        self._start_time = None
        self.last_viewer_frame = None

    def ingest(self, snapshot, *, now: Optional[float] = None) -> ViewerFrame:
        """Convert a FrameSnapshot into ViewerFrame and update force history."""
        display = build_display_image(snapshot, self.arrow_background)
        h, w, aspect = image_shape_meta(display)

        fn = float(getattr(snapshot, "normal_force", 0.0))
        fx = float(getattr(snapshot, "shear_x", 0.0))
        fy = float(getattr(snapshot, "shear_y", 0.0))
        fn_cal = float(getattr(snapshot, "normal_force_calibrated", 0.0))
        fps = float(getattr(snapshot, "fps", 0.0))
        ts = float(getattr(snapshot, "timestamp", 0.0) or 0.0)
        if now is None:
            now = ts if ts > 0 else 0.0

        if self._start_time is None:
            self._start_time = now
        t = now - self._start_time
        self.force_history.push(t, fn, fx, fy)

        record = ensure_bgr(getattr(snapshot, "record_frame", None))
        depth = getattr(snapshot, "depth", None)

        frame = ViewerFrame(
            display_image=display,
            image_height=h,
            image_width=w,
            aspect_ratio=aspect,
            depth=depth,
            normal_force=fn,
            shear_x=fx,
            shear_y=fy,
            normal_force_calibrated=fn_cal,
            fps=fps,
            timestamp=ts,
            record_frame=record,
        )
        self.last_viewer_frame = frame
        return frame

    def plot_state(self) -> Optional[ForcePlotState]:
        return self.force_history.plot_state()
