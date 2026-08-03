"""Discover USB cameras for the dashboard (Windows DSHOW/MSMF, Linux V4L2)."""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass

import cv2

DEFAULT_MAX_CAMERA_INDEX = 10


@dataclass(frozen=True)
class CameraInfo:
    index: int
    backend_name: str
    backend_api: int
    width: int
    height: int

    @property
    def source(self) -> str:
        return str(self.index)

    def label(self) -> str:
        return f"{self.index} ({self.width}x{self.height}) [{self.backend_name}]"


@contextlib.contextmanager
def _suppress_opencv_noise():
    """Hide OpenCV VideoCapture probe warnings (stderr + OpenCV log)."""
    prev_level = None
    set_level = None
    try:
        logging = getattr(getattr(cv2, "utils", None), "logging", None)
        if logging is not None:
            set_level = getattr(logging, "setLogLevel", None)
            get_level = getattr(logging, "getLogLevel", None)
            silent = getattr(logging, "LOG_LEVEL_SILENT", 0)
            if set_level is not None:
                if get_level is not None:
                    prev_level = get_level()
                set_level(silent)
    except Exception:
        prev_level = None

    devnull = open(os.devnull, "w")
    try:
        with contextlib.redirect_stderr(devnull):
            stderr_fd = sys.stderr.fileno()
            saved_fd = os.dup(stderr_fd)
            try:
                os.dup2(devnull.fileno(), stderr_fd)
                yield
            finally:
                os.dup2(saved_fd, stderr_fd)
                os.close(saved_fd)
    finally:
        devnull.close()
        if set_level is not None and prev_level is not None:
            try:
                set_level(prev_level)
            except Exception:
                pass


def _backend_candidates() -> list[tuple[str, int]]:
    candidates: list[tuple[str, int]] = []
    if sys.platform == "win32":
        if hasattr(cv2, "CAP_DSHOW"):
            candidates.append(("DSHOW", cv2.CAP_DSHOW))
        if hasattr(cv2, "CAP_MSMF"):
            candidates.append(("MSMF", cv2.CAP_MSMF))
    elif sys.platform.startswith("linux"):
        # Prefer v4l2 for USB camera indices on Linux.
        if hasattr(cv2, "CAP_V4L2"):
            candidates.append(("V4L2", cv2.CAP_V4L2))
    if not candidates:
        candidates.append(("ANY", cv2.CAP_ANY))
    return candidates


def _try_open(index: int, backend_name: str, backend_api: int) -> CameraInfo | None:
    cap = cv2.VideoCapture(index, backend_api)
    if not cap.isOpened():
        cap.release()
        return None
    ok, frame = cap.read()
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if not ok or frame is None:
        if width <= 0 or height <= 0:
            cap.release()
            return None
    else:
        h, w = frame.shape[:2]
        width = width or int(w)
        height = height or int(h)
    cap.release()
    return CameraInfo(
        index=index,
        backend_name=backend_name,
        backend_api=backend_api,
        width=width,
        height=height,
    )


def list_cameras(max_index: int = DEFAULT_MAX_CAMERA_INDEX) -> list[CameraInfo]:
    """Probe indices ``0 .. max_index`` and return working cameras."""
    found: list[CameraInfo] = []
    seen_indices: set[int] = set()
    backends = _backend_candidates()

    with _suppress_opencv_noise():
        for index in range(0, max_index + 1):
            for backend_name, backend_api in backends:
                info = _try_open(index, backend_name, backend_api)
                if info is None:
                    continue
                if index in seen_indices:
                    break
                found.append(info)
                seen_indices.add(index)
                break
    return found


def pick_default_camera(cameras: list[CameraInfo], preferred: str | None = None) -> str | None:
    if not cameras:
        return None
    preferred = (preferred or "").strip()
    if preferred:
        for cam in cameras:
            if cam.source == preferred:
                return cam.source
    return cameras[0].source
