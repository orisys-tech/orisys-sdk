"""2D Qt sensor monitor window (image + force curves)."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

try:
    import pyqtgraph as pg
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "PyQtGraph is not installed. Please install it using 'pip install pyqt5 pyqtgraph'."
    ) from exc

from gui.sensors import create_sensor_adapter
from gui.widgets.log_panel import TeeStream, WidgetLogHandler, make_log_widget
from gui.widgets.qt_pixmap import ndarray_to_pixmap, pixmap_keep_aspect

from .backend import (
    PLOT_BUFFER_POINTS,
    PLOT_WINDOW_SEC,
    QtViewerBackend,
    panel_width_for_aspect,
)
from .styles import CURVE_THEME_COLOR, STYLE


class QtViewerWindow(QMainWindow):
    """2D monitor: flow/image panel + FN/FX/FY curves driven by QtViewerBackend."""

    def __init__(self, args, log_file):
        super().__init__()
        self.setWindowTitle("Orisys SDK")
        self.setStyleSheet(STYLE)

        logo_path = Path(__file__).resolve().parents[3] / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        self.sensor_adapter = None
        self._last_snapshot = None
        self._last_viewer_frame = None
        self._display_aspect = 1.0
        self._source_pixmap = None
        self.args = args

        self.is_save = False
        self.frame_count = 0
        self.writer = None
        self.save_path = None

        self.viewer_backend = QtViewerBackend(
            npoints=PLOT_BUFFER_POINTS,
            lowpass_cutoff_hz=getattr(args, "cutoff", 10.0),
        )

        self._setup_ui()
        self._create_plots()

        self.camera_edit.setText(args.video)
        self.config_edit.setText(args.config)
        self.cal_edit.setText(args.cal)

        self.log_handler = WidgetLogHandler(self.log_widget)
        sys.stdout = TeeStream(log_file, self.log_handler)
        sys.stderr = sys.stdout

        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        self._running = False

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        bar = QHBoxLayout()
        bar.setSpacing(8)

        self.btn_camera = QPushButton("摄像机")
        self.btn_camera.setObjectName("btnCamera")
        self.btn_camera.clicked.connect(self._select_camera)
        bar.addWidget(self.btn_camera)
        self.camera_edit = QLineEdit("1")
        self.camera_edit.setPlaceholderText("摄像头编号 或 视频路径")
        bar.addWidget(self.camera_edit, 1)

        self.btn_config = QPushButton("配置")
        self.btn_config.setObjectName("btnConfig")
        self.btn_config.clicked.connect(self._select_config)
        bar.addWidget(self.btn_config)
        self.config_edit = QLineEdit("./config/ddjx01.json")
        bar.addWidget(self.config_edit, 1)

        self.btn_reset = QPushButton("重置")
        self.btn_reset.setObjectName("btnReset")
        self.btn_reset.setEnabled(False)
        self.btn_reset.clicked.connect(self._on_reset)
        bar.addWidget(self.btn_reset)
        self.cal_edit = QLineEdit("./config/ddjx01.npy")
        bar.addWidget(self.cal_edit, 1)

        self.btn_start = QPushButton("启动")
        self.btn_start.setObjectName("btnStart")
        self.btn_start.clicked.connect(self._on_start)
        bar.addWidget(self.btn_start)

        self.btn_stop = QPushButton("暂停")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._on_stop)
        bar.addWidget(self.btn_stop)

        bg_caption = QLabel("背景")
        bg_caption.setObjectName("toolbarCaption")
        bar.addWidget(bg_caption)
        self.bg_combo = QComboBox()
        self.bg_combo.setObjectName("bgCombo")
        self.bg_combo.addItem("纯色背景", "pure_color")
        self.bg_combo.addItem("采集图像", "captured")
        self.bg_combo.setCurrentIndex(0)
        self.bg_combo.currentIndexChanged.connect(self._on_arrow_background_changed)
        bar.addWidget(self.bg_combo)

        root_layout.addLayout(bar)

        v_splitter = QSplitter(Qt.Vertical)
        h_splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.arrows_label = QLabel()
        self.arrows_label.setObjectName("arrowsLabel")
        self.arrows_label.setMinimumSize(160, 160)
        self.arrows_label.setScaledContents(False)
        self.arrows_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.arrows_label)

        h_splitter.addWidget(left)

        pg.setConfigOption("background", "#000000")
        pg.setConfigOption("foreground", "#777777")
        pg.setConfigOptions(antialias=True)
        self.graph_widget = pg.GraphicsLayoutWidget()
        self.graph_widget.setMinimumWidth(300)
        h_splitter.addWidget(self.graph_widget)

        self.h_splitter = h_splitter
        v_splitter.addWidget(h_splitter)

        from gui.log_config import LOG_CONFIG

        self.log_widget = make_log_widget(LOG_CONFIG)
        v_splitter.addWidget(self.log_widget)

        v_splitter.setStretchFactor(0, 4)
        v_splitter.setStretchFactor(1, 1)
        root_layout.addWidget(v_splitter)

    def _create_plots(self):
        titles = ["法向力 (raw)", "切向力 X", "切向力 Y"]
        self.plots = []
        self.curves = []
        self.dot_glows = []
        self.dot_cores = []

        axis_pen = pg.mkPen(color=(38, 38, 38), width=1)
        label_font = QFont("SimHei", 9)

        for i, title in enumerate(titles):
            p = self.graph_widget.addPlot(title=None)
            p.setTitle(title, color="#999999", size="14pt")
            p.titleLabel.setFont(QFont("SimHei", 14))
            p.setLabel("bottom", "时间", units="s")
            p.getAxis("bottom").label.setFont(label_font)
            p.showAxis("top", False)
            p.showAxis("right", False)
            p.getAxis("left").setPen(axis_pen)
            p.getAxis("bottom").setPen(axis_pen)
            p.showGrid(x=False, y=True, alpha=0.12)

            tick_font = QFont("Consolas", 11)
            tick_font.setStyleHint(QFont.Monospace)
            p.getAxis("left").setTickFont(tick_font)
            p.getAxis("bottom").setTickFont(tick_font)

            line_pen = pg.mkPen(color=CURVE_THEME_COLOR, width=2)
            curve = p.plot(pen=line_pen, fillLevel=0)
            dot_glow = p.plot(
                [],
                [],
                pen=None,
                symbol="o",
                symbolSize=8,
                symbolPen=None,
                symbolBrush=(0, 229, 255, 76),
            )
            dot_core = p.plot(
                [],
                [],
                pen=None,
                symbol="o",
                symbolSize=4,
                symbolPen=None,
                symbolBrush=(255, 255, 255, 255),
            )

            p.setXRange(0, PLOT_WINDOW_SEC, padding=0)
            p.enableAutoRange(x=False, y=False)

            self.plots.append(p)
            self.curves.append(curve)
            self.dot_glows.append(dot_glow)
            self.dot_cores.append(dot_core)

            if i < 2:
                self.graph_widget.nextRow()

    def adjust_image_panel(self):
        """Size the left panel from the current image aspect ratio."""
        top_bar_h = 48
        log_h = self.log_widget.height()
        spacing = 20
        available = max(self.height() - top_bar_h - log_h - spacing, 160)
        image_w = panel_width_for_aspect(available, self._display_aspect, min_size=160)
        max_w = max(self.width() // 2, 160)
        image_w = min(image_w, max_w)
        self.h_splitter.setSizes([image_w, max(self.width() - image_w, 200)])
        self._render_display_pixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_display_pixmap()

    def _render_display_pixmap(self):
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        target = self.arrows_label.size()
        if target.width() < 2 or target.height() < 2:
            return
        self.arrows_label.setPixmap(pixmap_keep_aspect(self._source_pixmap, target))

    def _on_timer(self):
        if self.sensor_adapter is None:
            return

        snapshot = self.sensor_adapter.read()
        if snapshot is None:
            print("Failed to get image")
            return
        self._last_snapshot = snapshot

        viewer_frame = self.viewer_backend.ingest(snapshot, now=time.time())
        self._last_viewer_frame = viewer_frame
        first_image = self._source_pixmap is None
        aspect_changed = abs(viewer_frame.aspect_ratio - self._display_aspect) > 1e-3
        self._display_aspect = viewer_frame.aspect_ratio

        if self.is_save and self.writer is not None and snapshot.record_frame is not None:
            self.frame_count += 1
            save_img = snapshot.record_frame
            if len(save_img.shape) == 2 or (
                len(save_img.shape) == 3 and save_img.shape[2] == 1
            ):
                if len(save_img.shape) == 3:
                    save_img = save_img.squeeze(2)
                save_img = cv2.cvtColor(save_img, cv2.COLOR_GRAY2BGR)
            self.writer.write(save_img)

        print(
            f"FPS={viewer_frame.fps:.2f}, "
            f"法向力(raw)={viewer_frame.normal_force:.4f}, "
            f"切向力X={viewer_frame.shear_x:.4f}, "
            f"切向力Y={viewer_frame.shear_y:.4f}, "
            f"法向力(N)={viewer_frame.normal_force_calibrated:.6f}"
        )

        self._source_pixmap = ndarray_to_pixmap(viewer_frame.display_image, bgr=True)
        if first_image or aspect_changed:
            self.adjust_image_panel()
        else:
            self._render_display_pixmap()

        plot_state = self.viewer_backend.plot_state()
        if plot_state is None:
            return

        for i, curve in enumerate(self.curves):
            x = plot_state.times
            y = plot_state.values[:, i]
            curve.setData(x, y)
            ymin, ymax = plot_state.y_ranges[i]
            self.plots[i].setYRange(ymin, ymax)
            self.dot_glows[i].setData(x[-1:], y[-1:])
            self.dot_cores[i].setData(x[-1:], y[-1:])

        x0, x1 = plot_state.x_range
        for p in self.plots:
            p.setXRange(x0, x1, padding=0)

    def _on_start(self):
        if self._running:
            return
        self.btn_start.setText("启动中...")
        self.btn_start.setEnabled(False)
        QApplication.processEvents()

        try:
            src = self.camera_edit.text()
            cfg = self.config_edit.text()
            cal = self.cal_edit.text()
            verbose = getattr(self.args, "verbose", True)
            sensor_type = getattr(self.args, "sensor_type", "orisys")
            self.sensor_adapter = create_sensor_adapter(
                sensor_type,
                video=src,
                config_name=cfg,
                cal_path=cal,
                verbose=verbose,
            )
            self.sensor_adapter.start()
        except Exception as e:
            self.btn_start.setText("启动")
            self.btn_start.setEnabled(True)
            self.sensor_adapter = None
            print(f"启动失败: {e}")
            return

        self.viewer_backend.reset()
        self._running = True
        self.timer.start(10)
        self.btn_start.setText("启动")
        self.btn_stop.setEnabled(True)
        self.btn_reset.setEnabled(True)
        print(
            f"▶ 启动 — sensor_type={getattr(self.args, 'sensor_type', 'orisys')}, "
            f"摄像机={src}, 配置={cfg}, 标定={cal}"
        )

    def _on_stop(self):
        if not self._running:
            return
        self._running = False
        self.timer.stop()
        self.btn_stop.setText("停止中...")
        self.btn_stop.setEnabled(False)
        QApplication.processEvents()

        if self.sensor_adapter is not None:
            self.sensor_adapter.close()
            self.sensor_adapter = None
        self._last_snapshot = None

        self.btn_start.setEnabled(True)
        self.btn_stop.setText("暂停")
        self.btn_reset.setEnabled(False)
        print("⏸ 已暂停")

    def _select_camera(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "data",
            "视频 (*.mp4 *.avi *.mov);;所有文件 (*)",
        )
        if path:
            self.camera_edit.setText(path)

    def _select_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            "config",
            "JSON (*.json);;所有文件 (*)",
        )
        if path:
            self.config_edit.setText(path)

    def _on_reset(self):
        if self.sensor_adapter is None or not self._running:
            print("请先启动传感器后再重置追踪器。")
            return
        self.sensor_adapter.reset()
        print("追踪器已重置。")

    def _on_arrow_background_changed(self, _index: int) -> None:
        value = self.bg_combo.currentData()
        if value not in ("pure_color", "captured"):
            return
        self.viewer_backend.set_arrow_background(value)
        if self._last_snapshot is None:
            return
        viewer_frame = self.viewer_backend.rebuild_display(self._last_snapshot)
        self._last_viewer_frame = viewer_frame
        aspect_changed = abs(viewer_frame.aspect_ratio - self._display_aspect) > 1e-3
        self._display_aspect = viewer_frame.aspect_ratio
        self._source_pixmap = ndarray_to_pixmap(viewer_frame.display_image, bgr=True)
        if aspect_changed:
            self.adjust_image_panel()
        else:
            self._render_display_pixmap()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif key == Qt.Key_Q:
            print("\n正在退出示例程序...")
            self.close()
        elif key == Qt.Key_S:
            self._start_recording()
        elif key == Qt.Key_E:
            self._stop_recording()
        elif key == Qt.Key_R:
            self._on_reset()
        else:
            super().keyPressEvent(event)

    def _start_recording(self):
        if self.sensor_adapter is None:
            print("请先启动采集")
            return
        self.save_path = "./data/pulse_test.mp4"
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

        save_img = None
        if self._last_snapshot is not None:
            save_img = self._last_snapshot.record_frame
        if save_img is None:
            print("当前没有可用帧，无法确定录像尺寸。")
            return

        temp_img = save_img.copy()
        if len(temp_img.shape) == 2 or (
            len(temp_img.shape) == 3 and temp_img.shape[2] == 1
        ):
            if len(temp_img.shape) == 3:
                temp_img = temp_img.squeeze(2)
            temp_img = cv2.cvtColor(temp_img, cv2.COLOR_GRAY2BGR)

        fh, fw = temp_img.shape[:2]
        self.writer = cv2.VideoWriter(
            self.save_path,
            cv2.VideoWriter_fourcc(*"mp4v"),
            30,
            (fw, fh),
        )
        if self.writer.isOpened():
            self.is_save = True
            print(f"开始录像：{self.save_path}")
        else:
            print(f"无法创建录像文件：{self.save_path}")
            self.writer = None

    def _stop_recording(self):
        self.is_save = False
        if self.writer is not None:
            self.writer.release()
            self.writer = None
        if self.save_path is not None:
            print(f"录像结束：{self.save_path}，总帧数：{self.frame_count}")
        else:
            print(f"录像结束，总帧数：{self.frame_count}")
        self.frame_count = 0

    def closeEvent(self, event):
        self.timer.stop()
        if self.writer is not None:
            self.writer.release()
        if self.sensor_adapter is not None:
            self.sensor_adapter.close()
            self.sensor_adapter = None
        event.accept()


def run_viewer(args, *, log_dir: str | Path | None = None) -> int:
    """Launch the 2D Qt viewer and block until the window closes."""
    from gui.app import get_or_create_qapp

    if log_dir is None:
        log_dir = Path(__file__).resolve().parents[3] / "scripts" / "logs"
    else:
        log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"qt_viewer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    sys.stdout = log_file
    sys.stderr = sys.stdout

    print("\n按键说明：Q 退出 | R 重置追踪器 | S 开始录像 | E 结束录像 | ESC 全屏")

    app = get_or_create_qapp("Orisys SDK")
    window = QtViewerWindow(args, log_file)
    window.showFullScreen()
    QApplication.processEvents()
    window.adjust_image_panel()
    return app.exec_()
