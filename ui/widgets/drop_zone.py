"""
Drag-and-drop zone widget for file imports.
"""

from pathlib import Path
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from Resources.styles import DROP_ZONE_STYLES


class DropZoneWidget(QFrame):
    """
    A drag-and-drop zone widget for accepting files.

    Signals:
        files_dropped: Emitted when valid files are dropped (list of paths)
        clicked: Emitted when the zone is clicked
    """

    files_dropped = pyqtSignal(list)
    clicked = pyqtSignal()

    def __init__(
        self,
        accepted_extensions: list,
        title: str = "Drop files here",
        subtitle: str = "or click to browse",
        parent=None
    ):
        super().__init__(parent)
        self.accepted_extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                                    for ext in accepted_extensions]
        self._setup_ui(title, subtitle)
        self._set_style('normal')

    def _setup_ui(self, title: str, subtitle: str):
        """Set up the widget UI."""
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(100)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(5)

        # Title label
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.title_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        # Subtitle label
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)

        # Info label (for showing accepted types)
        ext_text = ", ".join(self.accepted_extensions)
        self.info_label = QLabel(f"Accepted: {ext_text}")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.info_label.font()
        font.setPointSize(8)
        self.info_label.setFont(font)
        layout.addWidget(self.info_label)

    def _set_style(self, style_name: str):
        """Apply a style to the widget."""
        style = DROP_ZONE_STYLES.get(style_name, DROP_ZONE_STYLES['normal'])
        self.setStyleSheet(style)

    def set_title(self, title: str):
        """Update the title text."""
        self.title_label.setText(title)

    def set_subtitle(self, subtitle: str):
        """Update the subtitle text."""
        self.subtitle_label.setText(subtitle)

    def set_enabled(self, enabled: bool):
        """Enable or disable the drop zone."""
        super().setEnabled(enabled)
        self.setAcceptDrops(enabled)
        self._set_style('normal' if enabled else 'disabled')
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if enabled
            else Qt.CursorShape.ForbiddenCursor
        )

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter - check if files are acceptable."""
        if not self.isEnabled():
            event.ignore()
            return

        if event.mimeData().hasUrls():
            # Check if any files match accepted extensions
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in self.accepted_extensions:
                        event.acceptProposedAction()
                        self._set_style('hover')
                        return

        event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        """Handle drag leave - restore normal style."""
        self._set_style('normal')

    def dropEvent(self, event: QDropEvent):
        """Handle drop - emit signal with valid files."""
        self._set_style('normal')

        if not self.isEnabled():
            return

        files = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.suffix.lower() in self.accepted_extensions:
                    files.append(str(path))

        if files:
            self.files_dropped.emit(files)
            event.acceptProposedAction()

    def mousePressEvent(self, event: QMouseEvent):
        """Handle click - emit clicked signal."""
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class PDFDropZone(DropZoneWidget):
    """Pre-configured drop zone for PDF files."""

    def __init__(self, parent=None):
        super().__init__(
            accepted_extensions=['.pdf'],
            title="Drop PDF files here",
            subtitle="or click to browse for files",
            parent=parent
        )


class ExcelDropZone(DropZoneWidget):
    """Pre-configured drop zone for Excel/CSV files."""

    def __init__(self, parent=None):
        super().__init__(
            accepted_extensions=['.xlsx', '.xls', '.csv'],
            title="Drop Excel or CSV files here",
            subtitle="or click to browse",
            parent=parent
        )
