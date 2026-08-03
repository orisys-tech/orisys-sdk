"""Embedded PyQtGraph force charts for the Qt dashboard."""

from __future__ import annotations

import numpy as np
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QSizePolicy

from ..layout import DashboardLayout, LAYOUT
from ..styles import LOG_FONT_PRIMARY, UI_FONT_PRIMARY
from pipeline.frame import FingerFrameView
from viz.signal_filters import lowpass_filter


def _require_pyqtgraph():
    try:
        import pyqtgraph as pg
    except ImportError as exc:
        raise ImportError(
            "PyQtGraph is not installed. Install with: pip install pyqt5 pyqtgraph"
        ) from exc
    return pg


class ForceChartWidget:
    """Rolling normal/shear force charts as an embeddable QWidget."""

    def __init__(
        self,
        *,
        layout: DashboardLayout = LAYOUT,
        lowpass_cutoff_hz: float = 5.0,
        parent=None,
    ):
        pg = _require_pyqtgraph()
        pg.setConfigOption("background", "#000000")
        pg.setConfigOption("foreground", "#777777")
        pg.setConfigOptions(antialias=True)

        self._layout = layout
        self._pg = pg
        self.npoints = layout.plot_buffer_points
        self.sample_rate_hz = layout.plot_sample_rate_hz
        self.lowpass_cutoff_hz = lowpass_cutoff_hz
        self._plot_window_sec = self.npoints / self.sample_rate_hz
        self._plot_sample_count = 0
        self._y_range_alpha = layout.y_range_smooth_alpha
        self._y_range_smooth: list[tuple[float, float] | None] = [None, None, None]

        self.widget = pg.GraphicsLayoutWidget(parent=parent)
        charts = layout.top_slot("charts")
        self.set_panel_size(charts.width_px, charts.height_px)
        self._init_plot_buffer()
        self._create_plots()

    def set_panel_size(self, width: int, height: int) -> None:
        """Apply layout width/height; height 0 means fill top-row height."""
        width = max(int(width), 64)
        self.widget.setFixedWidth(width)
        if height > 0:
            self.widget.setFixedHeight(height)
            self.widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        else:
            self.widget.setMaximumHeight(16777215)
            self.widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def _init_plot_buffer(self) -> None:
        self.data = np.full((self.npoints, 2, 3), np.nan, dtype=np.float64)
        self._plot_sample_count = 0
        self._time_origin: float | None = None
        self._y_range_smooth = [None, None, None]

    def _create_plots(self) -> None:
        pg = self._pg
        layout = self._layout
        titles = ["Normal Deformation", "X Deformation", "Y Deformation"]
        self.plots = []
        self.curves = []
        self.dot_glows = []
        self.dot_cores = []

        axis_pen = pg.mkPen(color=(38, 38, 38), width=1)
        label_font = QFont(UI_FONT_PRIMARY, layout.chart_axis_label_font_pt)
        title_pt = layout.chart_title_font_pt

        for i, title in enumerate(titles):
            plot = self.widget.addPlot(title=None)
            plot.setTitle(title, color="#999999", size=f"{title_pt}pt")
            plot.titleLabel.setFont(QFont(UI_FONT_PRIMARY, title_pt))
            plot.setLabel("bottom", "Time", units="s")
            plot.getAxis("bottom").label.setFont(label_font)
            plot.showAxis("top", False)
            plot.showAxis("right", False)
            plot.getAxis("left").setPen(axis_pen)
            plot.getAxis("bottom").setPen(axis_pen)
            plot.showGrid(x=False, y=True, alpha=0.12)

            tick_font = QFont(LOG_FONT_PRIMARY, layout.chart_tick_font_pt)
            tick_font.setStyleHint(QFont.Monospace)
            plot.getAxis("left").setTickFont(tick_font)
            plot.getAxis("bottom").setTickFont(tick_font)

            line_pen = pg.mkPen(color=layout.curve_color, width=2)
            curve = plot.plot(pen=line_pen, fillLevel=0)
            dot_glow = plot.plot(
                [],
                [],
                pen=None,
                symbol="o",
                symbolSize=8,
                symbolPen=None,
                symbolBrush=(0, 229, 255, 76),
            )
            dot_core = plot.plot(
                [],
                [],
                pen=None,
                symbol="o",
                symbolSize=4,
                symbolPen=None,
                symbolBrush=(255, 255, 255, 255),
            )
            plot.setXRange(0, self._plot_window_sec, padding=0)
            plot.enableAutoRange(x=False, y=False)

            self.plots.append(plot)
            self.curves.append(curve)
            self.dot_glows.append(dot_glow)
            self.dot_cores.append(dot_core)
            if i < 2:
                self.widget.nextRow()

    def reset(self) -> None:
        self._init_plot_buffer()
        for plot in self.plots:
            plot.setXRange(0, self._plot_window_sec, padding=0)

    def update_frame(self, frame: FingerFrameView) -> None:
        if self._time_origin is None:
            self._time_origin = frame.timestamp

        if self._plot_sample_count < self.npoints:
            idx = self._plot_sample_count
            self.data[idx, 0, :] = frame.timestamp
            self.data[idx, 1, 0] = frame.fnormal
            self.data[idx, 1, 1] = frame.fshearx
            self.data[idx, 1, 2] = frame.fsheary
            self._plot_sample_count += 1
        else:
            for channel in range(3):
                self.data[:-1, 0, channel] = self.data[1:, 0, channel]
                self.data[:-1, 1, channel] = self.data[1:, 1, channel]
            self.data[-1, 0, :] = frame.timestamp
            self.data[-1, 1, 0] = frame.fnormal
            self.data[-1, 1, 1] = frame.fshearx
            self.data[-1, 1, 2] = frame.fsheary

        n = self._plot_sample_count
        if n == 0 or self._time_origin is None:
            return

        layout = self._layout
        data_plot = self.data[:n]
        times = data_plot[:, 0, 0] - self._time_origin
        x_end = float(times[-1])
        if x_end < self._plot_window_sec:
            x_start = 0.0
            x_end = self._plot_window_sec
        else:
            x_start = x_end - self._plot_window_sec

        for channel in range(3):
            y = lowpass_filter(
                data_plot[:, 1, channel].copy(),
                self.lowpass_cutoff_hz,
                sample_rate_hz=self.sample_rate_hz,
            )

            curve = self.curves[channel]
            curve.setData(times, y)
            finite = np.isfinite(y)
            if not np.any(finite):
                continue
            ymin, ymax = float(np.min(y[finite])), float(np.max(y[finite]))
            if self._y_range_smooth[channel] is None:
                self._y_range_smooth[channel] = (ymin, ymax)
            else:
                prev_min, prev_max = self._y_range_smooth[channel]
                alpha = self._y_range_alpha
                ymin = alpha * ymin + (1 - alpha) * prev_min
                ymax = alpha * ymax + (1 - alpha) * prev_max
            span = ymax - ymin
            if span < layout.y_axis_min_span:
                mid = (ymin + ymax) / 2
                half = layout.y_axis_min_span / 2
                ymin = mid - half
                ymax = mid + half
            self._y_range_smooth[channel] = (ymin, ymax)
            pad = max((ymax - ymin) * 0.12, 0.01)
            self.plots[channel].setYRange(ymin - pad, ymax + pad)
            self.dot_glows[channel].setData(times[-1:], y[-1:])
            self.dot_cores[channel].setData(times[-1:], y[-1:])

        for plot in self.plots:
            plot.setXRange(x_start, x_end, padding=0)
