"""Background Open3D mesh rendering for the Qt dashboard."""

from __future__ import annotations

import numpy as np
from PyQt5.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal


class MeshRenderWorker(QThread):
    """Render finger mesh off the GUI thread; drops stale frames."""

    rgb_ready = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._stop = False
        self._wake = False
        self._renderer = None
        self._pending: dict | None = None

    def set_renderer(self, renderer) -> None:
        with QMutexLocker(self._mutex):
            self._renderer = renderer

    def clear_renderer(self) -> None:
        with QMutexLocker(self._mutex):
            self._renderer = None
            self._pending = None

    def submit(self, *, flow, scalar_map, centroid, centroid_found, fnormal, valid_mask=None) -> None:
        with QMutexLocker(self._mutex):
            self._pending = {
                "flow": flow,
                "scalar_map": scalar_map,
                "centroid": centroid,
                "centroid_found": centroid_found,
                "fnormal": fnormal,
                "valid_mask": valid_mask,
            }
            self._wake = True
        if not self.isRunning():
            self.start()

    def stop_worker(self) -> None:
        with QMutexLocker(self._mutex):
            self._stop = True
            self._wake = True
        self.wait(2000)

    def run(self) -> None:
        while True:
            with QMutexLocker(self._mutex):
                if self._stop:
                    break
                if not self._wake or self._renderer is None or self._pending is None:
                    self.msleep(1)
                    continue
                job = self._pending
                self._pending = None
                self._wake = False
                renderer = self._renderer

            rgb = renderer.render(
                flow=job["flow"],
                scalar_map=job["scalar_map"],
                centroid=job["centroid"],
                centroid_found=job["centroid_found"],
                fnormal=job["fnormal"],
                valid_mask=job["valid_mask"],
            )
            self.rgb_ready.emit(np.ascontiguousarray(rgb))

            with QMutexLocker(self._mutex):
                if self._pending is not None:
                    self._wake = True
