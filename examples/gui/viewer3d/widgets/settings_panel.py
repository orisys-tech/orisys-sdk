"""Settings side panel for the finger dashboard."""

from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from orisys.finger import DEFAULT_FINGER_EXPORT_DIR
from viz.render_2d import ArrowBackground

from ..layout import DashboardLayout, LAYOUT
from ..mesh_view_state import MeshViewState
from ..transport_icons import reset_icon, transport_icon

_PLAY_PAUSE_BUTTON_NAME = "btnPlayPause"
_PLAY_PAUSE_ICON_PX = 18
_PLAY_PAUSE_ICON_COLORS = {
    "run": "#4caf84",
    "starting": "#555555",
    "pause": "#ff9800",
}


class SettingsPanelWidget(QWidget):
    """Right-side settings: log, sources, and 3D view controls."""

    log_visibility_changed = pyqtSignal(bool)
    free_rotation_changed = pyqtSignal(bool)
    arrow_background_changed = pyqtSignal(str)
    view_reset_requested = pyqtSignal()
    browse_video_requested = pyqtSignal()
    browse_config_requested = pyqtSignal()
    browse_finger_assets_requested = pyqtSignal()
    browse_csv_dir_requested = pyqtSignal()
    csv_record_toggled = pyqtSignal(bool)
    camera_refresh_requested = pyqtSignal()
    camera_selection_changed = pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        *,
        layout: DashboardLayout = LAYOUT,
        mesh_state: MeshViewState | None = None,
        show_log: bool = True,
    ):
        super().__init__(parent)
        self._layout = layout
        self._mesh_state = mesh_state or MeshViewState.from_layout(layout)
        self.setObjectName("settingsPanel")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        title = QLabel(layout.settings_panel_title)
        title.setObjectName("settingsTitle")
        root.addWidget(title)

        control_row = QHBoxLayout()
        control_row.setSpacing(8)

        self.btn_play_pause = QPushButton()
        self.btn_play_pause.setObjectName(_PLAY_PAUSE_BUTTON_NAME)
        self.btn_play_pause.setFixedSize(36, 32)
        self.btn_play_pause.setIconSize(QSize(_PLAY_PAUSE_ICON_PX, _PLAY_PAUSE_ICON_PX))
        control_row.addWidget(self.btn_play_pause)

        self.btn_reset_tracker = QPushButton("Reset Sensor")
        self.btn_reset_tracker.setToolTip("Reset tracker")
        self.btn_reset_tracker.setEnabled(False)
        control_row.addWidget(self.btn_reset_tracker, 1)
        root.addLayout(control_row)

        self.show_log_check = QCheckBox("Show log panel")
        self.show_log_check.setChecked(show_log)
        self.show_log_check.toggled.connect(self.log_visibility_changed.emit)
        root.addWidget(self.show_log_check)

        self.show_flow_arrows_check = QCheckBox("Show displacement arrows")
        self.show_flow_arrows_check.setChecked(self._mesh_state.flow_arrows_enabled)
        self.show_flow_arrows_check.toggled.connect(self._mesh_state.set_flow_arrows_enabled)
        root.addWidget(self.show_flow_arrows_check)

        root.addWidget(self._caption("UV arrow background"))
        self.arrow_background_combo = QComboBox()
        for label, value in (
            ("Unrolled", "unrolled"),
            ("Pure color", "pure_color"),
        ):
            self.arrow_background_combo.addItem(label, value)
        self.set_arrow_background(layout.arrow_background)
        self.arrow_background_combo.currentIndexChanged.connect(self._emit_arrow_background_changed)
        root.addWidget(self.arrow_background_combo)

        root.addWidget(self._caption("Video source"))
        video_row = QHBoxLayout()
        video_row.setSpacing(6)
        self.camera_combo = QComboBox()
        self.camera_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.camera_combo.setToolTip("Select an available camera")
        # activated fires on user pick even when the index is unchanged (file → live override).
        self.camera_combo.activated.connect(self._on_camera_combo_changed)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_combo_changed)
        video_row.addWidget(self.camera_combo, 1)
        self.btn_refresh_cameras = QPushButton("Refresh")
        self.btn_refresh_cameras.setFixedWidth(64)
        self.btn_refresh_cameras.setToolTip("Re-scan available cameras")
        self.btn_refresh_cameras.clicked.connect(self.camera_refresh_requested.emit)
        video_row.addWidget(self.btn_refresh_cameras)
        self.btn_browse_video = QPushButton("…")
        self.btn_browse_video.setFixedWidth(32)
        self.btn_browse_video.setToolTip("Browse video file")
        self.btn_browse_video.clicked.connect(self.browse_video_requested.emit)
        video_row.addWidget(self.btn_browse_video)
        root.addLayout(video_row)

        self.video_file_label = QLabel("")
        self.video_file_label.setObjectName("settingsCaption")
        self.video_file_label.setWordWrap(True)
        self.video_file_label.hide()
        root.addWidget(self.video_file_label)

        self._source_mode = "camera"  # "camera" | "file"
        self._video_file_path = ""
        self._updating_camera_options = False

        root.addWidget(self._caption("Config"))
        config_row = QHBoxLayout()
        config_row.setSpacing(6)
        self.config_edit = QLineEdit("finger")
        config_row.addWidget(self.config_edit, 1)
        self.btn_browse_config = QPushButton("…")
        self.btn_browse_config.setFixedWidth(32)
        self.btn_browse_config.setToolTip("Browse config JSON")
        self.btn_browse_config.clicked.connect(self.browse_config_requested.emit)
        config_row.addWidget(self.btn_browse_config)
        root.addLayout(config_row)

        # Optional calibration path is kept for future re-enablement but hidden for now.
        self.cal_edit = QLineEdit("")
        self.cal_edit.setPlaceholderText("Optional calibration path")
        self.cal_edit.hide()

        root.addWidget(self._caption("Finger assets"))
        finger_assets_row = QHBoxLayout()
        finger_assets_row.setSpacing(6)
        self.finger_assets_edit = QLineEdit(DEFAULT_FINGER_EXPORT_DIR)
        self.finger_assets_edit.setPlaceholderText("Blender export bundle directory")
        finger_assets_row.addWidget(self.finger_assets_edit, 1)
        self.btn_browse_finger_assets = QPushButton("…")
        self.btn_browse_finger_assets.setFixedWidth(32)
        self.btn_browse_finger_assets.setToolTip("Browse finger asset directory")
        self.btn_browse_finger_assets.clicked.connect(self.browse_finger_assets_requested.emit)
        finger_assets_row.addWidget(self.btn_browse_finger_assets)
        root.addLayout(finger_assets_row)

        root.addWidget(self._caption("CSV save directory"))
        csv_dir_row = QHBoxLayout()
        csv_dir_row.setSpacing(6)
        self.csv_dir_edit = QLineEdit("./outputs/csv")
        self.csv_dir_edit.setPlaceholderText("Directory for CSV recordings")
        csv_dir_row.addWidget(self.csv_dir_edit, 1)
        self.btn_browse_csv_dir = QPushButton("…")
        self.btn_browse_csv_dir.setFixedWidth(32)
        self.btn_browse_csv_dir.setToolTip("Browse CSV save directory")
        self.btn_browse_csv_dir.clicked.connect(self.browse_csv_dir_requested.emit)
        csv_dir_row.addWidget(self.btn_browse_csv_dir)
        root.addLayout(csv_dir_row)

        self.btn_csv_record = QPushButton("Record CSV")
        self.btn_csv_record.setToolTip("Start writing contact/force CSV")
        self.btn_csv_record.setEnabled(False)
        self.btn_csv_record.clicked.connect(self._on_csv_toggle_clicked)
        root.addWidget(self.btn_csv_record)
        self._csv_recording = False
        self._pipeline_running = False

        root.addSpacing(4)
        rotate_row = QHBoxLayout()
        rotate_row.setSpacing(6)
        self.free_rotate_check = QCheckBox("Free rotate 3D view")
        self.free_rotate_check.toggled.connect(self.free_rotation_changed.emit)
        rotate_row.addWidget(self.free_rotate_check, 1)

        self.btn_reset_view = QPushButton()
        self.btn_reset_view.setObjectName("btnResetView")
        self.btn_reset_view.setToolTip("Reset 3D mesh camera")
        self.btn_reset_view.setIcon(reset_icon("#999999"))
        self.btn_reset_view.setIconSize(QSize(14, 14))
        self.btn_reset_view.setFixedSize(28, 28)
        self.btn_reset_view.clicked.connect(self.view_reset_requested.emit)
        rotate_row.addWidget(self.btn_reset_view)
        root.addLayout(rotate_row)

        root.addStretch()

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("settingsCaption")
        return label

    def set_panel_size(self, width: int, height: int) -> None:
        self.setFixedSize(max(int(width), 64), max(int(height), 64))

    def set_play_pause_state(self, state: str) -> None:
        """``run`` = green play, ``starting`` = grey disabled play, ``pause`` = orange pause."""
        btn = self.btn_play_pause
        if state == "run":
            btn.setToolTip("Run")
            btn.setEnabled(True)
        elif state == "starting":
            btn.setToolTip("Starting…")
            btn.setEnabled(False)
        elif state == "pause":
            btn.setToolTip("Pause")
            btn.setEnabled(True)
        else:
            raise ValueError(f"unknown play/pause state: {state!r}")

        kind = "pause" if state == "pause" else "play"
        btn.setText("")
        btn.setIcon(transport_icon(kind, _PLAY_PAUSE_ICON_COLORS[state]))
        btn.setProperty("playState", state)
        style = btn.style()
        style.unpolish(btn)
        style.polish(btn)
        btn.update()

    def set_camera_options(self, cameras, selected_value: str | None = None) -> None:
        """Populate camera combo from discovered cameras.

        ``cameras`` items may be objects with ``.source`` / ``.label()`` or
        ``(source, label)`` tuples.
        """
        self._updating_camera_options = True
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()

        sources: list[str] = []
        for cam in cameras:
            if hasattr(cam, "source") and callable(getattr(cam, "label", None)):
                source = str(cam.source)
                label = str(cam.label())
            else:
                source, label = cam
                source = str(source)
                label = str(label)
            self.camera_combo.addItem(label, source)
            sources.append(source)

        preferred = (selected_value or "").strip()
        idx = self.camera_combo.findData(preferred) if preferred else -1
        if idx < 0 and self.camera_combo.count() > 0:
            idx = 0
        if idx >= 0:
            self.camera_combo.setCurrentIndex(idx)
            # File mode is cleared only when we intentionally select a camera.
            if self._source_mode != "file":
                self._source_mode = "camera"
                self._video_file_path = ""
                self.video_file_label.hide()
        self.camera_combo.setEnabled(self.camera_combo.count() > 0)
        self.camera_combo.blockSignals(False)
        self._updating_camera_options = False

    def set_video_source(self, value: str) -> None:
        """Set current video source (camera index string or file path)."""
        value = (value or "").strip()
        if not value:
            return
        # Numeric camera index → select in combo if present; else keep as preferred text via adding.
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            idx = self.camera_combo.findData(value)
            if idx >= 0:
                self._source_mode = "camera"
                self._video_file_path = ""
                self.video_file_label.hide()
                self.camera_combo.blockSignals(True)
                self.camera_combo.setCurrentIndex(idx)
                self.camera_combo.blockSignals(False)
            else:
                # Not yet scanned / not present: remember as pending camera selection.
                self._source_mode = "camera"
                self._video_file_path = ""
                self.video_file_label.hide()
            return

        # Treat as video file path.
        self._source_mode = "file"
        self._video_file_path = value
        self.video_file_label.setText(f"File: {value}")
        self.video_file_label.show()

    def selected_camera_source(self) -> str:
        data = self.camera_combo.currentData()
        return str(data) if data is not None else ""

    def video_source(self) -> str:
        if self._source_mode == "file" and self._video_file_path:
            return self._video_file_path
        return self.selected_camera_source()

    def has_usable_source(self) -> bool:
        if self._source_mode == "file" and self._video_file_path:
            return True
        return bool(self.selected_camera_source())

    def is_file_source(self) -> bool:
        return self._source_mode == "file" and bool(self._video_file_path)

    def set_camera_controls_enabled(self, enabled: bool) -> None:
        self.btn_refresh_cameras.setEnabled(enabled)
        self.btn_browse_video.setEnabled(enabled)
        self.camera_combo.setEnabled(enabled and self.camera_combo.count() > 0)

    def _on_camera_combo_changed(self, _index: int) -> None:
        if self._updating_camera_options:
            return
        source = self.selected_camera_source()
        if not source:
            return
        self._source_mode = "camera"
        self._video_file_path = ""
        self.video_file_label.hide()
        self.camera_selection_changed.emit(source)

    def set_config_path(self, value: str) -> None:
        self.config_edit.setText(value)

    def set_calibration_path(self, value: str) -> None:
        self.cal_edit.setText(value or "")

    def set_finger_export_dir(self, value: str) -> None:
        self.finger_assets_edit.setText(value)

    def set_finger_export_dir_enabled(self, enabled: bool) -> None:
        self.finger_assets_edit.setEnabled(enabled)
        self.btn_browse_finger_assets.setEnabled(enabled)

    def set_csv_save_dir(self, value: str) -> None:
        self.csv_dir_edit.setText(value)

    def set_csv_controls_for_pipeline(self, running: bool) -> None:
        """Update CSV controls from pipeline start/stop."""
        self._pipeline_running = bool(running)
        if not self._pipeline_running:
            self._csv_recording = False
        self._refresh_csv_controls()

    def set_csv_recording(self, recording: bool) -> None:
        """Update CSV controls after a successful start/stop of recording."""
        self._csv_recording = bool(recording) and self._pipeline_running
        self._refresh_csv_controls()

    def _refresh_csv_controls(self) -> None:
        self.btn_csv_record.setEnabled(self._pipeline_running)
        if self._csv_recording:
            self.btn_csv_record.setText("Stop CSV")
            self.btn_csv_record.setToolTip("Stop CSV recording")
            self.btn_csv_record.setProperty("recording", True)
        else:
            self.btn_csv_record.setText("Record CSV")
            self.btn_csv_record.setToolTip("Start writing contact/force CSV")
            self.btn_csv_record.setProperty("recording", False)
        style = self.btn_csv_record.style()
        style.unpolish(self.btn_csv_record)
        style.polish(self.btn_csv_record)
        self.btn_csv_record.update()

        dir_enabled = not self._csv_recording
        self.csv_dir_edit.setEnabled(dir_enabled)
        self.btn_browse_csv_dir.setEnabled(dir_enabled)

    def _on_csv_toggle_clicked(self) -> None:
        if not self._pipeline_running:
            return
        self.csv_record_toggled.emit(not self._csv_recording)

    def _emit_arrow_background_changed(self, _index: int) -> None:
        value = self.arrow_background_combo.currentData()
        if value:
            self.arrow_background_changed.emit(value)

    def set_arrow_background(self, value: ArrowBackground) -> None:
        idx = self.arrow_background_combo.findData(value)
        if idx < 0:
            return
        self.arrow_background_combo.blockSignals(True)
        self.arrow_background_combo.setCurrentIndex(idx)
        self.arrow_background_combo.blockSignals(False)

    def arrow_background(self) -> ArrowBackground:
        value = self.arrow_background_combo.currentData()
        return value if value else "unrolled"

    def config_path(self) -> str:
        return self.config_edit.text().strip()

    def calibration_path(self) -> str:
        return self.cal_edit.text().strip()

    def finger_export_dir(self) -> str:
        return self.finger_assets_edit.text().strip()

    def csv_save_dir(self) -> str:
        return self.csv_dir_edit.text().strip()

    def preference_state(self) -> dict:
        """Serialize user-facing settings suitable for preference.json."""
        return {
            "video_source": self.video_source(),
            "config_path": self.config_path(),
            "finger_assets_dir": self.finger_export_dir(),
            "csv_save_dir": self.csv_save_dir(),
            "show_log": bool(self.show_log_check.isChecked()),
            "show_flow_arrows": bool(self.show_flow_arrows_check.isChecked()),
            "arrow_background": self.arrow_background(),
            "free_rotate": bool(self.free_rotate_check.isChecked()),
        }

    def apply_preference_state(self, state: dict | None) -> None:
        """Restore user-facing settings from preference.json."""
        if not isinstance(state, dict) or not state:
            return

        show_log = state.get("show_log")
        if isinstance(show_log, bool):
            self.show_log_check.blockSignals(True)
            self.show_log_check.setChecked(show_log)
            self.show_log_check.blockSignals(False)

        show_flow = state.get("show_flow_arrows")
        if isinstance(show_flow, bool):
            self.show_flow_arrows_check.blockSignals(True)
            self.show_flow_arrows_check.setChecked(show_flow)
            self.show_flow_arrows_check.blockSignals(False)
            self._mesh_state.set_flow_arrows_enabled(show_flow)

        arrow_bg = state.get("arrow_background")
        if isinstance(arrow_bg, str) and arrow_bg:
            self.set_arrow_background(arrow_bg)  # type: ignore[arg-type]

        free_rotate = state.get("free_rotate")
        if isinstance(free_rotate, bool):
            self.free_rotate_check.blockSignals(True)
            self.free_rotate_check.setChecked(free_rotate)
            self.free_rotate_check.blockSignals(False)

        config_path = state.get("config_path")
        if isinstance(config_path, str) and config_path.strip():
            self.set_config_path(config_path.strip())

        assets = state.get("finger_assets_dir")
        if isinstance(assets, str) and assets.strip():
            self.set_finger_export_dir(assets.strip())

        csv_dir = state.get("csv_save_dir")
        if isinstance(csv_dir, str) and csv_dir.strip():
            self.set_csv_save_dir(csv_dir.strip())

        video = state.get("video_source")
        if isinstance(video, str) and video.strip():
            self.set_video_source(video.strip())
