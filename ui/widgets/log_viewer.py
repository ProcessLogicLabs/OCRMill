"""
Log viewer widget for displaying activity logs.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QTextCursor, QFont


class LogViewerWidget(QWidget):
    """
    A widget for displaying log messages with auto-scroll.

    Features:
    - Monospace font for consistent formatting
    - Auto-scroll to newest messages
    - Clear button
    - Line count display
    - Maximum line limit to prevent memory issues
    """

    MAX_LINES = 10000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._line_count = 0

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Text display
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Set monospace font
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(font)

        layout.addWidget(self.text_edit)

        # Bottom toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)

        self.line_count_label = QLabel("0 lines")
        toolbar.addWidget(self.line_count_label)

        toolbar.addStretch()

        self.clear_button = QPushButton("Clear Log")
        self.clear_button.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_button)

        layout.addLayout(toolbar)

    @pyqtSlot(str)
    def append_message(self, message: str):
        """
        Append a message to the log.

        Args:
            message: The message to append (timestamp should be included)
        """
        # Append the message
        self.text_edit.appendPlainText(message)
        self._line_count += 1

        # Auto-scroll to bottom
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)

        # Update line count
        self.line_count_label.setText(f"{self._line_count} lines")

        # Trim old lines if exceeding max
        if self._line_count > self.MAX_LINES:
            self._trim_old_lines()

    def _trim_old_lines(self):
        """Remove old lines when exceeding the maximum."""
        # Remove oldest 10% of lines
        lines_to_remove = self.MAX_LINES // 10

        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(lines_to_remove):
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor
            )
        cursor.removeSelectedText()

        self._line_count -= lines_to_remove
        self.line_count_label.setText(f"{self._line_count} lines")

    @pyqtSlot()
    def clear(self):
        """Clear all log messages."""
        self.text_edit.clear()
        self._line_count = 0
        self.line_count_label.setText("0 lines")

    def get_text(self) -> str:
        """Get all log text."""
        return self.text_edit.toPlainText()

    def set_max_lines(self, max_lines: int):
        """Set the maximum number of lines to keep."""
        self.MAX_LINES = max_lines


class CompactLogViewer(QPlainTextEdit):
    """
    A simpler log viewer without the toolbar.
    Useful for embedded log displays.
    """

    MAX_LINES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._line_count = 0

        # Set monospace font
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

    @pyqtSlot(str)
    def append_message(self, message: str):
        """Append a message to the log."""
        self.appendPlainText(message)
        self._line_count += 1

        # Auto-scroll
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

        # Trim if needed
        if self._line_count > self.MAX_LINES:
            self._trim_old_lines()

    def _trim_old_lines(self):
        """Remove old lines when exceeding maximum."""
        lines_to_remove = self.MAX_LINES // 10

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(lines_to_remove):
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor
            )
        cursor.removeSelectedText()
        self._line_count -= lines_to_remove
