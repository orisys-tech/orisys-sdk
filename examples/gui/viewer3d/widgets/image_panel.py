"""Square 1:1 image panel host for dashboard viewports."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from gui.widgets.qt_pixmap import pixmap_keep_aspect


class ImagePanel(QWidget):
    """Fixed square widget that displays an image at 1:1 aspect ratio."""

    def __init__(
        self,
        *,
        title: str = "",
        object_name: str = "panelLabel",
        default_side: int = 256,
        min_side: int = 64,
        parent=None,
    ):
        super().__init__(parent)
        self._side = default_side
        self._min_side = min_side
        self._source_pixmap: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(title)
        self.label.setObjectName(object_name)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        self.set_side_length(self._side)

    def set_side_length(self, side: int) -> None:
        self.set_fixed_size(side, side)

    def set_fixed_size(self, width: int, height: int) -> None:
        width = max(int(width), self._min_side)
        height = max(int(height), self._min_side)
        if width == self.width() and height == self.height() and width == self._side:
            return
        self._side = width
        self.setFixedSize(width, height)
        self.label.setFixedSize(width, height)
        self.on_side_length_changed(min(width, height))
        self._refresh_pixmap()

    @property
    def side_length(self) -> int:
        return self._side

    def on_side_length_changed(self, side: int) -> None:
        """Hook for subclasses (e.g. resize an offscreen renderer)."""

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source_pixmap = pixmap
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        self.label.setPixmap(pixmap_keep_aspect(self._source_pixmap, self.label.size()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_pixmap()
