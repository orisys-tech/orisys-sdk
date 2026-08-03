"""Pure numpy→BGR render helpers for finger 2D panels (no window I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import cv2
import numpy as np
import orisys

if TYPE_CHECKING:
    from pipeline.frame import FingerFrameView

ArrowBackground = Literal["unrolled", "pure_color"]


@dataclass(frozen=True)
class ArrowCanvasColors:
    """BGR fill colors for synthetic UV arrow background (``background='pure_color'``)."""

    outside_bgr: tuple[int, int, int] = (0, 0, 0)
    uv_bgr: tuple[int, int, int] = (255, 255, 255)


DEFAULT_ARROW_CANVAS_COLORS = ArrowCanvasColors()


def depth_colormap(depth_map, colormap=cv2.COLORMAP_JET) -> np.ndarray:
    """Normalize a scalar map to uint8 and apply an OpenCV colormap."""
    values = np.asarray(depth_map)
    if values.size == 0:
        return np.zeros((1, 1, 3), dtype=np.uint8)
    if values.max() > values.min():
        normalized = ((values - values.min()) / (values.max() - values.min()) * 255).astype(np.uint8)
    else:
        normalized = np.zeros_like(values, dtype=np.uint8)
    return cv2.applyColorMap(normalized, colormap)


def frame_to_bgr(frame: np.ndarray) -> np.ndarray:
    """Convert a grayscale or single-channel frame to BGR for display/recording."""
    if frame is None:
        raise ValueError("frame is None")
    if len(frame.shape) == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if len(frame.shape) == 3 and frame.shape[2] == 1:
        return cv2.cvtColor(frame.squeeze(2), cv2.COLOR_GRAY2BGR)
    return frame


def render_depth_panel(depth_map):
    """Return a BGR depth colormap image."""
    return depth_colormap(depth_map)


def _as_bgr(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(int(np.clip(c, 0, 255)) for c in color[:3])


def _arrow_background(
    frame: FingerFrameView,
    background: ArrowBackground,
    *,
    canvas_colors: ArrowCanvasColors = DEFAULT_ARROW_CANVAS_COLORS,
) -> np.ndarray:
    """Return the BGR canvas for UV arrow drawing."""
    if background == "unrolled":
        return frame.unrolled
    if background != "pure_color":
        raise ValueError(f"unknown arrow background: {background!r}")
    h, w = frame.unrolled.shape[:2]
    outside = np.array(_as_bgr(canvas_colors.outside_bgr), dtype=np.uint8)
    uv = np.array(_as_bgr(canvas_colors.uv_bgr), dtype=np.uint8)
    canvas = np.broadcast_to(outside, (h, w, 3)).copy()
    mask = frame.valid_mask
    if mask is None:
        return canvas
    mask = np.asarray(mask, dtype=bool)
    if mask.shape != (h, w):
        mask_u8 = mask.astype(np.uint8)
        if mask_u8.ndim > 2:
            mask_u8 = mask_u8[:, :, 0]
        mask = cv2.resize(mask_u8, (w, h), interpolation=cv2.INTER_NEAREST).astype(bool)
    canvas[mask] = uv
    return canvas


def render_uv_arrows(
    frame: FingerFrameView,
    *,
    flow_threshold: float = 0.4,
    grid_spacing: int = 20,
    arrow_scale: float = 1.0,
    background: ArrowBackground = "unrolled",
    canvas_colors: ArrowCanvasColors = DEFAULT_ARROW_CANVAS_COLORS,
):
    """Return a BGR UV arrow panel from a FingerFrameView (uses frame.valid_mask)."""
    return orisys.util.draw_arrows(
        _arrow_background(frame, background, canvas_colors=canvas_colors),
        frame.flow,
        threshold=flow_threshold,
        grid_spacing=grid_spacing,
        arrow_scale=arrow_scale,
        valid_mask=frame.valid_mask,
        below_threshold_color = (128, 0, 0),
        colormap = cv2.COLORMAP_JET
    )


def render_contact_panel(img, contour, centroid):
    """Return a BGR contact overlay on the raw sensor image."""
    return orisys.util.draw_contact(img, contour, centroid)
