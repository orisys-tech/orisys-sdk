"""Qt pixmap conversion helpers (no widget dependencies)."""

from __future__ import annotations

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap


def ndarray_to_pixmap(image: np.ndarray, *, bgr: bool = True) -> QPixmap:
    """Convert a numpy image to QPixmap for QLabel display."""
    arr = np.ascontiguousarray(image)
    if arr.ndim == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        bgr = True
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[:, :, :3]
    if bgr:
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    else:
        rgb = arr
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def pixmap_keep_aspect(pixmap: QPixmap, size) -> QPixmap:
    """Scale a pixmap to fit ``size`` without changing aspect ratio."""
    if size.width() <= 0 or size.height() <= 0:
        return pixmap
    return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
