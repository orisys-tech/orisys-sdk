"""PyQtGraph real-time force chart window for examples."""

from __future__ import annotations

import numpy as np


def _require_pyqtgraph():
    try:
        import pyqtgraph as pg
    except ImportError as exc:
        raise ImportError(
            "PyQtGraph is not installed. Install with: pip install pyqt5 pyqtgraph"
        ) from exc
    return pg


class ForceChartWindow:
    """Rolling normal/shear force charts backed by PyQtGraph."""

    def __init__(
        self,
        *,
        npoints: int = 100,
        sample_rate_hz: float = 30.0,
        title: str = "Orisys 实时力曲线",
        app_name: str = "Orisys Plot Example",
    ) -> None:
        pg = _require_pyqtgraph()
        pg.setConfigOption("background", "k")
        pg.setConfigOption("foreground", "w")

        self._pg = pg
        self.npoints = npoints
        self.sample_rate_hz = sample_rate_hz
        self.app = pg.mkQApp(app_name)
        self.win = pg.GraphicsLayoutWidget(show=True, title=title)
        self.win.setWindowTitle(title)
        self.pen = pg.mkPen(color="w")

        self.data = np.zeros((npoints, 2, 3), dtype=np.float64)
        for channel in range(3):
            self.data[:, 0, channel] = np.linspace(-npoints, 0, npoints) / sample_rate_hz

        p1 = self.win.addPlot(title="Normal Deformation")
        p1.setLabel("bottom", "时间", units="s")
        self.win.nextRow()
        p2 = self.win.addPlot(title="X Deformation")
        p2.setLabel("bottom", "时间", units="s")
        self.win.nextRow()
        p3 = self.win.addPlot(title="Y Deformation")
        p3.setLabel("bottom", "时间", units="s")

        self._plots = (p1, p2, p3)
        self._curves = (p1.plot(pen=self.pen ), p2.plot(pen=self.pen ), p3.plot(pen=self.pen ))

    def push(self, timestamp: float, fn: float, fx: float, fy: float) -> None:
        for channel in range(3):
            self.data[:-1, 0, channel] = self.data[1:, 0, channel]
            self.data[:-1, 1, channel] = self.data[1:, 1, channel]
        self.data[-1, 0, :] = timestamp
        self.data[-1, 1, 0] = fn
        self.data[-1, 1, 1] = fx
        self.data[-1, 1, 2] = fy

    def refresh(self, display_data: np.ndarray | None = None) -> None:
        plot_data = self.data if display_data is None else display_data
        for channel, (plot, curve) in enumerate(zip(self._plots, self._curves)):
            curve.setData(plot_data[:, :, channel])
            plot.setYRange(float(plot_data[:, 1, channel].min()), float(plot_data[:, 1, channel].max()))
