"""Logging helpers for the finger dashboard."""

from __future__ import annotations

from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import QPlainTextEdit


class TeeStream:
    """Write to multiple text streams."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


class WidgetLogHandler:
    """Mirror print output into a QPlainTextEdit with pinned status lines at the bottom."""

    def __init__(self, widget: QPlainTextEdit):
        self.widget = widget
        self.buf = ""
        self._status_text: str | None = None
        self._status_block_count = 0

    def write(self, text: str):
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line:
                self._append_log_line(line)

    def flush(self):
        if self.buf:
            self._append_log_line(self.buf)
            self.buf = ""

    def set_status_line(self, text: str) -> None:
        """Update pinned bottom status (supports multi-line) without scrolling away."""
        text = text.rstrip("\n")
        self._remove_status_blocks()
        self.widget.appendPlainText(text)
        self._status_text = text
        self._status_block_count = max(1, text.count("\n") + 1)
        scrollbar = self.widget.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_status_line(self) -> None:
        self._remove_status_blocks()
        self._status_text = None
        self._status_block_count = 0

    def _remove_status_blocks(self) -> None:
        if self._status_block_count <= 0:
            return
        doc = self.widget.document()
        end = QTextCursor(doc)
        end.movePosition(QTextCursor.End)
        start = QTextCursor(doc)
        start.movePosition(QTextCursor.End)
        for _ in range(self._status_block_count):
            start.movePosition(QTextCursor.StartOfBlock)
            if start.position() > 0:
                start.movePosition(QTextCursor.Left)
        cursor = QTextCursor(doc)
        cursor.setPosition(start.position())
        cursor.setPosition(end.position(), QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self._status_block_count = 0

    def _append_log_line(self, line: str) -> None:
        status = self._status_text
        if status is not None:
            self.clear_status_line()
        self.widget.appendPlainText(line)
        if status is not None:
            self.set_status_line(status)


def make_log_widget(config=None) -> QPlainTextEdit:
    if config is None:
        from ..log_config import LOG_CONFIG

        config = LOG_CONFIG
    widget = QPlainTextEdit()
    widget.setReadOnly(True)
    widget.setMaximumBlockCount(config.max_lines)
    font = QFont(config.font_family, config.font_pt)
    font.setStyleHint(QFont.Monospace)
    widget.setFont(font)
    return widget
