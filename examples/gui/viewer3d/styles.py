"""Qt stylesheet for the finger dashboard."""

UI_FONT_STACK = '"Segoe UI Variable", "Segoe UI", "Inter", "Microsoft YaHei UI", sans-serif'
LOG_FONT_STACK = '"Cascadia Mono", "JetBrains Mono", "IBM Plex Mono", "Consolas", monospace'
UI_FONT_PRIMARY = "Segoe UI"
LOG_FONT_PRIMARY = "Cascadia Mono"

STYLE = """
QMainWindow {
    background-color: #000000;
}

QLabel#panelLabel, QLabel#meshViewport {
    border: 1px solid #262626;
    border-radius: 4px;
    background-color: #0b0b0b;
}

QWidget#settingsPanel {
    border: 1px solid #262626;
    border-radius: 4px;
    background-color: #0b0b0b;
}
QWidget#settingsPanel QLabel#settingsTitle {
    color: #cccccc;
    font-family: __UI_FONT__;
    font-size: 13px;
    font-weight: 600;
}
QWidget#settingsPanel QLabel#settingsCaption {
    color: #777777;
    font-family: __UI_FONT__;
    font-size: 11px;
}
QWidget#settingsPanel QCheckBox {
    color: #999999;
    font-family: __UI_FONT__;
    font-size: 12px;
    spacing: 6px;
}
QPushButton#btnResetView {
    padding: 2px;
}

QPushButton {
    background-color: #1a1a1a;
    color: #999999;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px 16px;
    font-family: __UI_FONT__;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #262626;
    color: #cccccc;
    border: 1px solid #555555;
}
QPushButton#btnPlayPause {
    background-color: #0d2818;
    color: #4caf84;
    border: 1px solid #1a4d30;
    padding: 4px 8px;
    font-size: 15px;
}
QPushButton#btnPlayPause:hover {
    background-color: #143d24;
    color: #6fd4a0;
}
QPushButton#btnPlayPause:disabled {
    background-color: #1a1a1a;
    color: #555555;
    border: 1px solid #333333;
}
QPushButton#btnPlayPause[playState="pause"] {
    background-color: #3d2808;
    color: #ff9800;
    border: 1px solid #6d4400;
}
QPushButton#btnPlayPause[playState="pause"]:hover {
    background-color: #523208;
    color: #ffb74d;
    border: 1px solid #8a5a00;
}
QPushButton#btnPlayPause[playState="pause"]:disabled {
    background-color: #1a1a1a;
    color: #555555;
    border: 1px solid #333333;
}
QLineEdit {
    background-color: #0d0d0d;
    color: #999999;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 5px 10px;
    font-family: __UI_FONT__;
    font-size: 13px;
}

GraphicsLayoutWidget {
    border: 1px solid #262626;
    border-radius: 4px;
}

QPlainTextEdit {
    background-color: #0b0b0b;
    color: #999999;
    border: 1px solid #262626;
    border-radius: 4px;
    font-family: __LOG_FONT__;
    font-size: 12px;
    padding: 8px;
    selection-background-color: #1a3a4a;
    selection-color: #cccccc;
}

QPlainTextEdit QScrollBar:vertical {
    background-color: #0b0b0b;
    width: 6px;
    margin: 1px;
    border-radius: 3px;
}
QPlainTextEdit QScrollBar::handle:vertical {
    background-color: #262626;
    border-radius: 3px;
    min-height: 30px;
}
QPlainTextEdit QScrollBar::handle:vertical:hover {
    background-color: #3a3a3a;
}
QPlainTextEdit QScrollBar::add-line:vertical,
QPlainTextEdit QScrollBar::sub-line:vertical {
    height: 0px;
}
QPlainTextEdit QScrollBar::add-page:vertical,
QPlainTextEdit QScrollBar::sub-page:vertical {
    background: none;
}

QSplitter::handle {
    background-color: #1a1a1a;
}
QSplitter::handle:vertical {
    height: 1px;
}
QSplitter::handle:horizontal {
    width: 1px;
}
""".replace("__UI_FONT__", UI_FONT_STACK).replace("__LOG_FONT__", LOG_FONT_STACK)
