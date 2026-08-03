"""Polygon ROI geometry helpers for rectifying tactile sensor frames."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


def load_json_config(path):
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_roi_polygon(config):
    """Return (points Nx2 float32, image_size [w,h]) from nested or legacy ROI fields."""
    roi = config.get("roi") if isinstance(config.get("roi"), dict) else config
    if not isinstance(roi, dict):
        raise ValueError("Config has no usable ROI section")

    image_size = roi.get("image_size") or config.get("camera", {}).get("resolution_raw")
    if image_size is None:
        raise ValueError("ROI image_size is missing")

    points = roi.get("points") or roi.get("polygon") or roi.get("roi_polygon")
    if points is None and roi.get("xyxy") is not None:
        x1, y1, x2, y2 = [int(v) for v in roi["xyxy"]]
        points = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    if not points:
        raise ValueError("ROI points are missing")

    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if pts.shape[0] < 4:
        raise ValueError(f"ROI needs at least 4 points, got {pts.shape[0]}")
    return pts, [int(image_size[0]), int(image_size[1])]


def scale_points(points, source_size, target_size):
    source_w, source_h = float(source_size[0]), float(source_size[1])
    target_w, target_h = float(target_size[0]), float(target_size[1])
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2).copy()
    if source_w > 0 and source_h > 0 and (source_w, source_h) != (target_w, target_h):
        pts[:, 0] *= target_w / source_w
        pts[:, 1] *= target_h / source_h
    return pts


def order_quad_points(points):
    """Order 4 points as TL, TR, BR, BL for perspective transforms."""
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if pts.shape[0] != 4:
        hull = cv2.convexHull(pts.astype(np.float32))
        rect = cv2.minAreaRect(hull)
        pts = cv2.boxPoints(rect).astype(np.float32)

    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]  # top-left
    ordered[2] = pts[np.argmax(s)]  # bottom-right
    ordered[1] = pts[np.argmin(diff)]  # top-right
    ordered[3] = pts[np.argmax(diff)]  # bottom-left
    return ordered


def rectified_output_size(config, points=None):
    """Prefer camera.resolution_stitch; fall back to ROI bounding box size."""
    stitch = config.get("camera", {}).get("resolution_stitch")
    if stitch is not None and len(stitch) >= 2:
        return int(stitch[0]), int(stitch[1])
    if points is not None:
        pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
        width = max(
            int(np.linalg.norm(pts[1] - pts[0])),
            int(np.linalg.norm(pts[2] - pts[3])),
            1,
        )
        height = max(
            int(np.linalg.norm(pts[3] - pts[0])),
            int(np.linalg.norm(pts[2] - pts[1])),
            1,
        )
        return width, height
    raise ValueError("Cannot determine rectified output size")


def build_roi_warp(points, source_image_size, frame_size, output_size):
    """
    Build a perspective transform that maps the ROI polygon in frame coords
    onto a rectangle of ``output_size`` (width, height).
    """
    frame_w, frame_h = int(frame_size[0]), int(frame_size[1])
    scaled = scale_points(points, source_image_size, (frame_w, frame_h))
    src = order_quad_points(scaled)
    out_w, out_h = int(output_size[0]), int(output_size[1])
    dst = np.array(
        [
            [0.0, 0.0],
            [out_w - 1.0, 0.0],
            [out_w - 1.0, out_h - 1.0],
            [0.0, out_h - 1.0],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(src, dst)
    return matrix, src, (out_w, out_h)


def warp_roi_to_rectangle(frame, matrix, output_size):
    out_w, out_h = int(output_size[0]), int(output_size[1])
    return cv2.warpPerspective(
        frame,
        matrix,
        (out_w, out_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def open_video_source(video):
    """Open a camera index or video file. Returns (cap, resolved_source)."""
    text = str(video).strip()
    if text.isdigit():
        source = int(text)
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(source)
    else:
        path = Path(text)
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {path}")
        source = str(path)
        cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video source: {video}")
    return cap, source
