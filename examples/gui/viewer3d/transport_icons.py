"""Monochrome play/pause icons for the dashboard toolbar (avoids Windows emoji glyphs)."""

from __future__ import annotations

import math
from typing import Literal

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

TransportKind = Literal["play", "pause"]

_DEFAULT_ICON_PX = 18


def transport_icon(kind: TransportKind, color: str, *, size: int = _DEFAULT_ICON_PX) -> QIcon:
    """Build a flat play triangle or pause bars in ``color`` (#rrggbb)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)

    if kind == "play":
        w = size * 0.52
        h = size * 0.60
        x0 = (size - w) * 0.58
        y0 = (size - h) / 2.0
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(x0, y0),
                    QPointF(x0, y0 + h),
                    QPointF(x0 + w, y0 + h / 2.0),
                ]
            )
        )
    else:
        bar_w = size * 0.17
        bar_h = size * 0.60
        gap = size * 0.14
        y0 = (size - bar_h) / 2.0
        x0 = (size - (2.0 * bar_w + gap)) / 2.0
        radius = max(1.0, size * 0.06)
        painter.drawRoundedRect(QRectF(x0, y0, bar_w, bar_h), radius, radius)
        painter.drawRoundedRect(QRectF(x0 + bar_w + gap, y0, bar_w, bar_h), radius, radius)

    painter.end()
    return QIcon(pixmap)


def reset_icon(color: str, *, size: int = 16) -> QIcon:
    """Build a circular reset / refresh arrow in ``color`` (#rrggbb)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    stroke = max(1.4, size * 0.11)
    pen = QPen(QColor(color), stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    margin = size * 0.2
    rect = QRectF(margin, margin, size - 2.0 * margin, size - 2.0 * margin)
    start_deg = 55.0
    painter.drawArc(rect, int(start_deg * 16), int(-280 * 16))

    cx, cy = rect.center().x(), rect.center().y()
    radius = rect.width() / 2.0
    angle_rad = math.radians(start_deg)
    tip_x = cx + radius * math.cos(angle_rad)
    tip_y = cy - radius * math.sin(angle_rad)
    tangent = angle_rad + math.pi / 2.0
    head = max(2.0, size * 0.18)
    wing = max(2.0, size * 0.14)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(tip_x, tip_y),
                QPointF(tip_x - head * math.cos(tangent) + wing * math.sin(tangent),
                        tip_y + head * math.sin(tangent) + wing * math.cos(tangent)),
                QPointF(tip_x - head * math.cos(tangent) - wing * math.sin(tangent),
                        tip_y + head * math.sin(tangent) - wing * math.cos(tangent)),
            ]
        )
    )

    painter.end()
    return QIcon(pixmap)
