"""Qt application bootstrap for Orisys example dashboards."""

from __future__ import annotations

import os
import sys


def fix_qt_plugin_path() -> None:
    """OpenCV redirects Qt to cv2/qt/plugins; use PyQt5's plugins instead."""
    try:
        from PyQt5.QtCore import QLibraryInfo

        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = QLibraryInfo.location(
            QLibraryInfo.PluginsPath
        )
    except Exception:
        path = os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH", "")
        if "cv2" in path.replace("\\", "/"):
            os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)


def get_or_create_qapp(app_name: str = "Orisys Finger Dashboard"):
    fix_qt_plugin_path()
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName(app_name)
    return app
