"""Styles for the 2D Qt sensor monitor."""

CURVE_THEME_COLOR = "#00E5FF"

STYLE = """
QMainWindow {
    background-color: #000000;
}

/* ---- 图像面板 ---- */
QLabel#arrowsLabel {
    border: 1px solid #262626;
    border-radius: 4px;
    background-color: #0b0b0b;
}

/* ---- 顶栏按钮 & 输入 ---- */
QPushButton {
    background-color: #1a1a1a;
    color: #999999;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px 16px;
    font-family: "SimHei";
    font-size: 13px;
}
QPushButton:hover {
    background-color: #262626;
    color: #cccccc;
    border: 1px solid #555555;
}
QPushButton#btnStart {
    background-color: #0d2818;
    color: #4caf84;
    border: 1px solid #1a4d30;
}
QPushButton#btnStart:hover {
    background-color: #143d24;
    color: #6fd4a0;
}
QPushButton#btnStart:disabled {
    background-color: #0f0f0f;
    color: #333333;
    border: 1px solid #222222;
}
QPushButton#btnStop {
    background-color: #2b1010;
    color: #e05555;
    border: 1px solid #4d1a1a;
}
QPushButton#btnStop:hover {
    background-color: #3d1818;
    color: #f07070;
}
QPushButton#btnStop:disabled {
    background-color: #0f0f0f;
    color: #333333;
    border: 1px solid #222222;
}
QLineEdit {
    background-color: #0d0d0d;
    color: #999999;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 5px 10px;
    font-size: 13px;
}

QLabel#toolbarCaption {
    color: #777777;
    font-family: "SimHei";
    font-size: 13px;
    padding-left: 4px;
}

QComboBox {
    background-color: #0d0d0d;
    color: #999999;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 5px 10px;
    font-family: "SimHei";
    font-size: 13px;
    min-width: 96px;
}
QComboBox:hover {
    background-color: #1a1a1a;
    color: #cccccc;
    border: 1px solid #555555;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #0d0d0d;
    color: #999999;
    border: 1px solid #333333;
    selection-background-color: #1a3a4a;
    selection-color: #cccccc;
}

/* ---- 力曲线容器 ---- */
GraphicsLayoutWidget {
    border: 1px solid #262626;
    border-radius: 4px;
}

/* ---- 日志面板 ---- */
QPlainTextEdit {
    background-color: #0b0b0b;
    color: #777777;
    border: 1px solid #262626;
    border-radius: 4px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 13px;
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
"""
