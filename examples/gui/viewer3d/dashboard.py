"""Unified Qt dashboard for the finger tactile example."""

from __future__ import annotations

import math
import sys
import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pipeline.config import PipelineConfig
from pipeline.csv_recorder import CsvRecorder
from pipeline.service import FingerPipeline

from gui.app_paths import resource_path
from .camera_discovery import list_cameras, pick_default_camera
from .preferences import get_preferred_video_source, load_preferences, save_preferences
from .layout import (
    DashboardLayout,
    LAYOUT,
    PANEL_SETUP,
    PanelSetup,
    top_row_splitter_sizes,
)
from .mesh_view_state import MeshViewState
from .styles import STYLE
from gui.widgets import TeeStream, WidgetLogHandler, make_log_widget
from .widgets import (
    ArrowPanelWidget,
    ForceChartWidget,
    MeshViewportWidget,
    SettingsPanelWidget,
)


class FingerDashboardWindow(QMainWindow):
    """Single-window finger demo: 3D mesh | UV arrows | force charts."""

    def __init__(
        self,
        config: PipelineConfig,
        *,
        layout: DashboardLayout = LAYOUT,
        log_file=None,
    ):
        super().__init__()
        self.config = config
        self.layout = layout
        self.pipeline = FingerPipeline(config)
        self.csv_recorder = CsvRecorder(config.csv_save_dir)
        self._running = False
        self._frame_index = 0
        self._wall_fps = 0.0
        self._wall_fps_alpha = 0.15

        self.setWindowTitle(layout.window_title)
        self.setStyleSheet(STYLE)

        logo_path = resource_path("logo.png")
        if logo_path.is_file():
            self.setWindowIcon(QIcon(str(logo_path)))

        self._setup_ui()
        self._wire_logging(log_file)

        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)

    def _setup_ui(self) -> None:
        layout = self.layout
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(layout.root_margin_px, layout.root_margin_px, layout.root_margin_px, layout.root_margin_px)
        root_layout.setSpacing(layout.root_spacing_px)

        setup = layout.panel_setup
        self._log_panel_visible = setup.log_panel.enabled
        self.mesh_state = MeshViewState.from_layout(layout)
        self.mesh_viewport = MeshViewportWidget(layout=layout, mesh_state=self.mesh_state)
        arrows_slot = layout.slot("arrows")
        self.arrow_panel: ArrowPanelWidget | None = None
        if arrows_slot is not None and arrows_slot.enabled:
            self.arrow_panel = ArrowPanelWidget(
                flow_threshold=layout.arrow_flow_threshold,
                background=layout.arrow_background,
                layout=layout,
            )
        self.force_charts = ForceChartWidget(layout=layout, lowpass_cutoff_hz=self.config.lowpass_cutoff_hz)
        self.log_widget = make_log_widget(layout.log_config)
        self.settings_panel = SettingsPanelWidget(
            layout=layout,
            mesh_state=self.mesh_state,
            show_log=self._log_panel_visible,
        )
        # CLI / pipeline defaults first, then overlay saved user preferences.
        self.settings_panel.set_video_source(str(self.config.video))
        self.settings_panel.set_config_path(self.config.config)
        self.settings_panel.set_calibration_path(self.config.calib or "")
        self.settings_panel.set_finger_export_dir(self.config.export_dir)
        self.settings_panel.set_csv_save_dir(self.config.csv_save_dir)

        self._preferences = load_preferences()
        self.settings_panel.apply_preference_state(self._preferences)
        self._log_panel_visible = bool(self.settings_panel.show_log_check.isChecked())
        self.mesh_viewport.set_free_rotation(bool(self.settings_panel.free_rotate_check.isChecked()))
        if self.arrow_panel is not None:
            self.arrow_panel.set_background(self.settings_panel.arrow_background())
        # Sync pipeline config fields from restored panel values.
        self.config.video = self.settings_panel.video_source() or self.config.video
        self.config.config = self.settings_panel.config_path() or self.config.config
        self.config.export_dir = self.settings_panel.finger_export_dir() or self.config.export_dir
        self.config.csv_save_dir = self.settings_panel.csv_save_dir() or self.config.csv_save_dir

        self.settings_panel.log_visibility_changed.connect(self._on_log_visibility_changed)
        self.settings_panel.free_rotation_changed.connect(self._on_free_rotation_changed)
        if self.arrow_panel is not None:
            self.settings_panel.arrow_background_changed.connect(self._on_arrow_background_changed)
        else:
            self.settings_panel.arrow_background_changed.connect(lambda _v: self._save_preferences())
        self.settings_panel.view_reset_requested.connect(self.mesh_viewport.reset_view)
        self.settings_panel.browse_video_requested.connect(self._select_camera)
        self.settings_panel.camera_refresh_requested.connect(self._refresh_cameras)
        self.settings_panel.camera_selection_changed.connect(self._on_camera_selection_changed)
        self.settings_panel.browse_config_requested.connect(self._select_config)
        self.settings_panel.browse_finger_assets_requested.connect(self._select_finger_assets)
        self.settings_panel.browse_csv_dir_requested.connect(self._select_csv_dir)
        self.settings_panel.csv_record_toggled.connect(self._on_csv_record_toggled)
        self.settings_panel.show_flow_arrows_check.toggled.connect(lambda _v: self._save_preferences())
        self.settings_panel.btn_play_pause.clicked.connect(self._on_play_pause_clicked)
        self.settings_panel.btn_reset_tracker.clicked.connect(self._on_reset)
        self.settings_panel.set_play_pause_state("run")
        self.settings_panel.set_csv_controls_for_pipeline(False)
        self._refresh_cameras(announce=True)

        self._panel_widgets: dict[str, QWidget] = {}
        self._panel_widgets["mesh"] = self.mesh_viewport
        if self.arrow_panel is not None:
            self._panel_widgets["arrows"] = self.arrow_panel
        self._panel_widgets["charts"] = self.force_charts.widget
        self._panel_widgets["settings"] = self.settings_panel
        self._panel_widgets["log"] = self.log_widget

        self.charts_column = QSplitter(Qt.Vertical)
        self.charts_column.addWidget(self.force_charts.widget)
        if setup.log_panel.enabled:
            self.charts_column.addWidget(self.log_widget)
            self.log_widget.setVisible(self._log_panel_visible)
            self.charts_column.setStretchFactor(0, setup.charts_log_stretch)
            self.charts_column.setStretchFactor(1, setup.log_stretch)
        self.charts_column.setChildrenCollapsible(False)

        h_splitter = QSplitter(Qt.Horizontal)
        for slot in setup.top_row.slots:
            if not slot.enabled:
                continue
            if slot.id == "charts":
                h_splitter.addWidget(self.charts_column)
            else:
                h_splitter.addWidget(self._panel_widgets[slot.id])
            h_splitter.setStretchFactor(h_splitter.count() - 1, slot.stretch)
        h_splitter.setChildrenCollapsible(setup.top_row.collapsible)
        self.h_splitter = h_splitter

        root_layout.addWidget(h_splitter)

        self.resize(*self._target_window_size())
        QTimer.singleShot(0, self._apply_panel_layout)

    def _set_log_panel_visible(self, visible: bool) -> None:
        self._log_panel_visible = bool(visible)
        self.log_widget.setVisible(self._log_panel_visible)
        QTimer.singleShot(0, self._apply_panel_layout)

    def _on_log_visibility_changed(self, visible: bool) -> None:
        self._set_log_panel_visible(visible)
        self._save_preferences()

    def _on_free_rotation_changed(self, enabled: bool) -> None:
        self.mesh_viewport.set_free_rotation(enabled)
        self._save_preferences()

    def _on_arrow_background_changed(self, value: str) -> None:
        if self.arrow_panel is not None:
            self.arrow_panel.set_background(value)
        self._save_preferences()

    def _save_preferences(self) -> None:
        prefs = self.settings_panel.preference_state()
        self._preferences = prefs
        save_preferences(prefs)
        # Keep in-memory pipeline config aligned with panel values.
        video = prefs.get("video_source")
        if isinstance(video, str) and video.strip():
            self.config.video = video.strip()
        config_path = prefs.get("config_path")
        if isinstance(config_path, str) and config_path.strip():
            self.config.config = config_path.strip()
        assets = prefs.get("finger_assets_dir")
        if isinstance(assets, str) and assets.strip():
            self.config.export_dir = assets.strip()
        csv_dir = prefs.get("csv_save_dir")
        if isinstance(csv_dir, str) and csv_dir.strip():
            self.config.csv_save_dir = csv_dir.strip()

    def _apply_panel_layout(self) -> None:
        setup = self.layout.panel_setup
        scale = self._layout_scale_factor()
        column_height = self._scaled_top_row_height(scale)
        charts_slot = self.layout.top_slot("charts")
        log_slot = setup.log_panel

        for slot in setup.top_row.slots:
            if not slot.enabled:
                continue
            if slot.id in ("mesh", "arrows"):
                self._panel_widgets[slot.id].set_fixed_size(
                    self._scaled_px(slot.width_px, scale),
                    column_height,
                )
            elif slot.id == "settings":
                settings_height = (
                    self._scaled_px(slot.height_px, scale) if slot.height_px > 0 else column_height
                )
                self.settings_panel.set_panel_size(
                    self._scaled_px(slot.width_px, scale),
                    settings_height,
                )

        if (
            self._log_panel_visible
            and log_slot.enabled
            and log_slot.height_px > 0
        ):
            self.log_widget.show()
            log_height = self._scaled_px(log_slot.height_px, scale)
            charts_height = self._scaled_px(charts_slot.height_px, scale)
            self.log_widget.setFixedHeight(log_height)
            self.force_charts.set_panel_size(
                self._scaled_px(charts_slot.width_px, scale),
                charts_height,
            )
            self.charts_column.setSizes([charts_height, log_height])
        else:
            self.log_widget.hide()
            self.force_charts.set_panel_size(
                self._scaled_px(charts_slot.width_px, scale),
                column_height,
            )
            self.charts_column.setSizes([column_height, 0])

        self.h_splitter.setSizes(
            [self._scaled_px(slot.width_px, scale) for slot in setup.top_row.slots if slot.enabled]
        )

    def _target_window_size(self) -> tuple[int, int]:
        """Match the top-level window to the fixed panel layout.

        The packaged Windows build can use different style metrics than a dev run,
        so sizing only from hard-coded window dimensions may stretch or compress the
        fixed-width panels. Derive the initial size from the actual panel layout and
        current splitter handle widths instead.
        """
        layout = self.layout
        enabled_slots = [slot for slot in layout.panel_setup.top_row.slots if slot.enabled]
        margins = self.centralWidget().layout().contentsMargins()

        width = sum(slot.width_px for slot in enabled_slots)
        width += max(len(enabled_slots) - 1, 0) * self.h_splitter.handleWidth()
        width += margins.left() + margins.right()

        height = layout.charts_column_height_px()
        if (
            self._log_panel_visible
            and layout.panel_setup.log_panel.enabled
            and layout.panel_setup.log_panel.height_px > 0
        ):
            height += self.charts_column.handleWidth()
        height += margins.top() + margins.bottom()

        return max(layout.window_width, width), max(layout.window_height, height)

    def _layout_scale_factor(self) -> float:
        """Uniformly scale the dashboard to fit the available content area.

        Only scale up when the user has explicitly maximized/fullscreened the
        window. Keeping normal windowed mode at scale 1 avoids a feedback loop
        where larger fixed-size child widgets increase the top-level size hint,
        which can make packaged Windows builds keep growing after launch.
        """
        if not (self.isMaximized() or self.isFullScreen()):
            return 1.0

        central = self.centralWidget()
        if central is None:
            return 1.0
        root_layout = central.layout()
        if root_layout is None:
            return 1.0

        margins = root_layout.contentsMargins()
        available_width = max(1, central.width() - margins.left() - margins.right())
        available_height = max(1, central.height() - margins.top() - margins.bottom())

        enabled_slots = [slot for slot in self.layout.panel_setup.top_row.slots if slot.enabled]
        base_width = sum(slot.width_px for slot in enabled_slots)
        base_width += max(len(enabled_slots) - 1, 0) * self.h_splitter.handleWidth()

        base_height = self.layout.charts_column_height_px()
        if (
            self._log_panel_visible
            and self.layout.panel_setup.log_panel.enabled
            and self.layout.panel_setup.log_panel.height_px > 0
        ):
            base_height += self.charts_column.handleWidth()
        if base_width <= 0 or base_height <= 0:
            return 1.0
        return min(available_width / base_width, available_height / base_height)

    @staticmethod
    def _scaled_px(value: int, scale: float) -> int:
        return max(int(round(value * scale)), 64)

    def _scaled_top_row_height(self, scale: float) -> int:
        return self._scaled_px(self.layout.charts_column_height_px(), scale)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_panel_layout)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_panel_layout)

    def _wire_logging(self, log_file) -> None:
        streams = []
        if log_file is not None:
            streams.append(log_file)
        self.log_handler = WidgetLogHandler(self.log_widget)
        streams.append(self.log_handler)
        sys.stdout = TeeStream(*streams)
        sys.stderr = sys.stdout

    def _set_play_pause_button(self, state: str) -> None:
        self.settings_panel.set_play_pause_state(state)

    def _on_play_pause_clicked(self) -> None:
        if self._running:
            self._on_stop()
        else:
            self._on_start()

    def _on_start(self) -> None:
        if self._running:
            return
        self._set_play_pause_button("starting")
        self.settings_panel.set_finger_export_dir_enabled(False)
        QApplication.processEvents()

        self.config.video = self.settings_panel.video_source()
        self.config.config = self.settings_panel.config_path()
        cal = self.settings_panel.calibration_path()
        self.config.calib = cal or None
        self.config.export_dir = self.settings_panel.finger_export_dir()
        self.config.csv_save_dir = self.settings_panel.csv_save_dir() or "./outputs/csv"

        if not self.config.video:
            self._set_play_pause_button("run")
            self.settings_panel.set_finger_export_dir_enabled(True)
            print("请先选择摄像机或视频文件。")
            return

        self._save_preferences()

        try:
            self.pipeline = FingerPipeline(self.config)
            self.pipeline.open()
            self.mesh_viewport.configure(self.pipeline)
            self.force_charts.reset()
            QTimer.singleShot(0, self._apply_panel_layout)
        except Exception as exc:
            self.mesh_viewport.close_renderer()
            self._set_play_pause_button("run")
            self.settings_panel.set_finger_export_dir_enabled(True)
            print(f"启动失败: {exc}")
            return

        self._running = True
        self._frame_index = 0
        self._wall_fps = 0.0
        self.timer.start(self.layout.timer_interval_ms)
        self._set_play_pause_button("pause")
        self.settings_panel.btn_reset_tracker.setEnabled(True)
        self.settings_panel.set_camera_controls_enabled(False)
        self.settings_panel.set_csv_controls_for_pipeline(True)
        print(
            f"▶ 启动 — 摄像机={self.config.video}, 配置={self.config.config}, "
            f"标定={self.config.calib or '(none)'}, 资产={self.config.export_dir}"
        )

    def _on_stop(self) -> None:
        if not self._running:
            return
        self._stop_csv_recording(announce=True)
        self._running = False
        self.timer.stop()
        self.log_handler.clear_status_line()
        self._set_play_pause_button("starting")
        QApplication.processEvents()

        self.mesh_viewport.close_renderer()
        self.pipeline.close()

        self._set_play_pause_button("run")
        self.settings_panel.btn_reset_tracker.setEnabled(False)
        self.settings_panel.set_finger_export_dir_enabled(True)
        self.settings_panel.set_camera_controls_enabled(True)
        self.settings_panel.set_csv_controls_for_pipeline(False)
        self._update_play_enabled_for_source()

    def _on_reset(self) -> None:
        if not self._running:
            print("请先启动传感器后再重置追踪器。")
            return
        self.pipeline.reset()
        print("追踪器已重置。")

    def _on_timer(self) -> None:
        if not self._running:
            return

        frame_t0 = time.perf_counter()
        frame, timings = self.pipeline.tick_timed()
        if frame is None:
            print("采集结束或读取失败。")
            self._on_stop()
            return

        self._frame_index += 1
        layout = self.layout
        profile = self.pipeline.profiler

        mesh_ms = 0.0
        if layout.mesh_render_stride <= 1 or self._frame_index % layout.mesh_render_stride == 0:
            mesh_ms = self.mesh_viewport.update_frame(frame)
            if profile is not None and mesh_ms > 0:
                profile.record("mesh", mesh_ms)

        arrows_ms = 0.0
        if self.arrow_panel is not None:
            t0 = time.perf_counter()
            self.arrow_panel.update_frame(frame)
            arrows_ms = (time.perf_counter() - t0) * 1000.0
        if profile is not None:
            profile.record("arrows", arrows_ms)

        charts_ms = 0.0
        if layout.chart_update_stride <= 1 or self._frame_index % layout.chart_update_stride == 0:
            t0 = time.perf_counter()
            self.force_charts.update_frame(frame)
            charts_ms = (time.perf_counter() - t0) * 1000.0
            if profile is not None:
                profile.record("charts", charts_ms)

        total_ms = (time.perf_counter() - frame_t0) * 1000.0
        instant_fps = 1000.0 / total_ms if total_ms > 0 else 0.0
        if self._wall_fps <= 0:
            self._wall_fps = instant_fps
        else:
            self._wall_fps = (
                self._wall_fps_alpha * instant_fps
                + (1.0 - self._wall_fps_alpha) * self._wall_fps
            )

        if profile is not None:
            profile.record("total", total_ms)
            self.pipeline.record_total_frame(total_ms)

        measurement = self.pipeline.measure_for_csv(frame, self._frame_index)
        if self.csv_recorder.is_recording:
            self.csv_recorder.write(measurement)

        flow_mag = 0.0
        if frame.flow.size:
            flow_mag = float((frame.flow[:, :, 0] ** 2 + frame.flow[:, :, 1] ** 2).mean() ** 0.5)

        contact_xyz_mm = None
        if (
            math.isfinite(measurement.contact_x)
            and math.isfinite(measurement.contact_y)
            and math.isfinite(measurement.contact_z)
        ):
            contact_xyz_mm = (
                measurement.contact_x,
                measurement.contact_y,
                measurement.contact_z,
            )

        log_cfg = layout.log_config
        if log_cfg.status_enabled:
            self.log_handler.set_status_line(
                log_cfg.format_status(
                    fps=frame.fps,
                    fnormal=frame.fnormal,
                    fshearx=frame.fshearx,
                    fsheary=frame.fsheary,
                    flow_rms=flow_mag,
                    mask_coverage=frame.mask_coverage,
                    wall_fps=self._wall_fps,
                    contact_xyz_mm=contact_xyz_mm,
                )
            )

    def _refresh_cameras(self, announce: bool = True) -> None:
        """Scan cameras and populate the settings dropdown."""
        keep_file = self.settings_panel.is_file_source()
        existing_file = self.settings_panel.video_source() if keep_file else ""

        preferred = None
        current = self.settings_panel.selected_camera_source()
        saved = get_preferred_video_source(self._preferences)
        cli_video = str(self.config.video).strip()
        if current.isdigit():
            preferred = current
        elif saved and str(saved).isdigit():
            preferred = str(saved)
        elif cli_video.isdigit():
            preferred = cli_video

        cameras = list_cameras()
        selected = pick_default_camera(cameras, preferred)

        self.settings_panel.set_camera_options(cameras, selected)
        if keep_file and existing_file:
            self.settings_panel.set_video_source(existing_file)
        elif selected:
            self.settings_panel.set_video_source(selected)
            self.config.video = selected
        elif not keep_file:
            self.config.video = ""

        self._update_play_enabled_for_source()
        self._save_preferences()
        if announce:
            if cameras:
                names = ", ".join(cam.label() for cam in cameras)
                print(f"已发现 {len(cameras)} 路摄像机：{names}")
                if selected and not keep_file:
                    print(f"当前摄像机：{selected}")
            else:
                print("未发现可用摄像机。可点击 Refresh 重扫，或通过 … 选择视频文件。")

    def _update_play_enabled_for_source(self) -> None:
        if self._running:
            return
        usable = self.settings_panel.has_usable_source()
        self.settings_panel.set_play_pause_state("run")
        self.settings_panel.btn_play_pause.setEnabled(usable)

    def _on_camera_selection_changed(self, camera_id: str) -> None:
        camera_id = str(camera_id).strip()
        if not camera_id:
            return
        # Explicit camera pick clears sticky file mode and persists the live source.
        self.settings_panel.set_video_source(camera_id)
        self.config.video = camera_id
        self._save_preferences()
        self._update_play_enabled_for_source()

    def _select_camera(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择视频文件",
            "data",
            "视频 (*.mp4 *.avi *.mov);;所有文件 (*)",
        )
        if path:
            self.settings_panel.set_video_source(path)
            self.config.video = path
            self._save_preferences()
            self._update_play_enabled_for_source()

    def _select_config(self) -> None:
        from .preferences import (
            default_finger_config,
            normalize_config_preference,
            packaged_finger_bundle_root,
        )

        start = packaged_finger_bundle_root()
        start_dir = str(start) if start is not None else "sensors/finger"
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            start_dir,
            "JSON (*.json);;所有文件 (*)",
        )
        if path:
            config = normalize_config_preference(path) or default_finger_config()
            self.settings_panel.set_config_path(config)
            self.config.config = config
            self._save_preferences()

    def _select_finger_assets(self) -> None:
        from .preferences import (
            default_finger_assets_dir,
            normalize_assets_preference,
            packaged_finger_assets_root,
        )

        start = packaged_finger_assets_root()
        start_dir = (
            str(start)
            if start is not None
            else (self.settings_panel.finger_export_dir() or default_finger_assets_dir())
        )
        path = QFileDialog.getExistingDirectory(
            self,
            "选择 finger 资产目录",
            start_dir,
        )
        if path:
            assets = normalize_assets_preference(path)
            self.settings_panel.set_finger_export_dir(assets)
            self.config.export_dir = assets
            self._save_preferences()

    def _select_csv_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择 CSV 保存目录",
            self.settings_panel.csv_save_dir() or "./outputs/csv",
        )
        if path:
            self.settings_panel.set_csv_save_dir(path)
            self.config.csv_save_dir = path
            self._save_preferences()

    def _on_csv_record_toggled(self, start: bool) -> None:
        if start:
            self._start_csv_recording()
        else:
            self._stop_csv_recording(announce=True)

    def _start_csv_recording(self) -> None:
        if not self._running:
            print("请先启动传感器后再记录 CSV。")
            self.settings_panel.set_csv_recording(False)
            return
        save_dir = self.settings_panel.csv_save_dir() or "./outputs/csv"
        self.config.csv_save_dir = save_dir
        try:
            path = self.csv_recorder.start(save_dir)
        except OSError as exc:
            print(f"无法开始 CSV 记录：{exc}")
            self.settings_panel.set_csv_recording(False)
            return
        self.settings_panel.set_csv_recording(True)
        print(f"开始 CSV 记录：{path}")

    def _stop_csv_recording(self, *, announce: bool = False) -> None:
        if not self.csv_recorder.is_recording:
            self.settings_panel.set_csv_recording(False)
            return
        path, count = self.csv_recorder.stop()
        self.settings_panel.set_csv_recording(False)
        if announce:
            if path is not None:
                print(f"CSV 记录结束：{path}，总行数：{count}")
            else:
                print(f"CSV 记录结束，总行数：{count}")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif key == Qt.Key_Q:
            print("\n正在退出...")
            self.close()
        elif key == Qt.Key_S:
            if self.pipeline.start_recording():
                print("开始录像。")
        elif key == Qt.Key_E:
            self.pipeline.stop_recording()
            print("录像结束。")
        elif key == Qt.Key_R:
            self._on_reset()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.timer.stop()
        self._stop_csv_recording(announce=True)
        self._save_preferences()
        self.mesh_viewport.close_renderer()
        self.pipeline.close()
        event.accept()


def run_dashboard(config: PipelineConfig, *, layout: DashboardLayout = LAYOUT) -> int:
    """Launch the unified finger dashboard and block until the window closes."""
    from gui.app import get_or_create_qapp

    print("\n按键说明：Q 退出 | R 重置追踪器 | S 开始录像 | E 结束录像 | ESC 全屏")
    print("GUI：Record CSV / Stop CSV 写入接触点与力到所选目录。")
    if config.profile:
        print(f"Profiling enabled (report every {config.profile_every} frames).")
        print("Log FPS= is end-to-end dashboard rate; sdk= is Sensor internal rate.")

    app = get_or_create_qapp()
    window = FingerDashboardWindow(config, layout=layout)
    window.show()
    QTimer.singleShot(0, window._apply_panel_layout)
    return app.exec_()
