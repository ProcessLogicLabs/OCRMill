"""
Animated Splash Screen for OCRMill.
Shows a spinning mill wheel with characters drifting toward center during startup.
"""

import math
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QPainterPath, QPixmap


class SpinningSplashScreen(QWidget):
    """
    Animated splash screen with spinning OCRMill logo.

    Features:
    - Spinning mill wheel in center
    - Characters (letters and numbers) orbiting and drifting toward center
    - Circular arrow indicators spinning
    - Progress text at bottom
    """

    # Colors from OCRMill theme
    TEAL = QColor(95, 158, 160)  # #5f9ea0
    TEAL_LIGHT = QColor(122, 184, 186)  # #7ab8ba
    PURPLE = QColor(107, 91, 149)  # #6b5b95
    PURPLE_LIGHT = QColor(139, 123, 181)  # #8b7bb5

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(400, 450)

        # Animation state
        self._wheel_angle = 0.0
        self._arrow_angle = 0.0
        self._char_radius = 140.0  # Start radius for characters
        self._char_angle_offset = 0.0
        self._progress = 0.0
        self._status_text = "Starting..."

        # Characters to display around the wheel
        self._outer_chars = ['A', '0', '1', 'B', '0', 'C', '1', 'D']
        self._inner_chars = ['E', '1', 'F', '0', 'G', '1', 'H', '0']

        # Animation timers
        self._wheel_timer = QTimer(self)
        self._wheel_timer.timeout.connect(self._update_wheel)
        self._wheel_timer.start(30)  # ~33 FPS

        self._char_timer = QTimer(self)
        self._char_timer.timeout.connect(self._update_chars)
        self._char_timer.start(50)

    def _update_wheel(self):
        """Update wheel and arrow rotation angles."""
        self._wheel_angle = (self._wheel_angle + 3) % 360
        self._arrow_angle = (self._arrow_angle + 2) % 360
        self.update()

    def _update_chars(self):
        """Update character orbit animation."""
        self._char_angle_offset = (self._char_angle_offset + 1) % 360

        # Gradually decrease radius as progress increases (characters drift toward center)
        target_radius = 140 - (self._progress * 0.6)  # Drift from 140 to ~80
        self._char_radius = self._char_radius + (target_radius - self._char_radius) * 0.05

        self.update()

    def set_progress(self, progress: float):
        """Set progress (0.0 to 100.0)."""
        self._progress = min(100.0, max(0.0, progress))
        self.update()

    def set_status(self, text: str):
        """Set status text."""
        self._status_text = text
        self.update()

    def paintEvent(self, event):
        """Draw the animated splash screen."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 200, 180  # Center of animation area

        # Draw semi-transparent background circle
        painter.setPen(Qt.PenStyle.NoPen)
        bg_color = QColor(30, 30, 30, 200)
        painter.setBrush(QBrush(bg_color))
        painter.drawEllipse(QPoint(cx, cy), 185, 185)

        # Draw outer ring of characters
        self._draw_char_ring(painter, cx, cy, self._outer_chars,
                            self._char_radius, self._char_angle_offset, 24, True)

        # Draw inner ring of characters (opposite direction)
        self._draw_char_ring(painter, cx, cy, self._inner_chars,
                            self._char_radius * 0.75, -self._char_angle_offset * 1.2, 18, False)

        # Draw circular arrows
        self._draw_arrows(painter, cx, cy)

        # Draw mill wheel
        self._draw_mill_wheel(painter, cx, cy)

        # Draw center hub
        self._draw_center_hub(painter, cx, cy)

        # Draw "OCRMill" text
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont("Segoe UI", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 370, 400, 40, Qt.AlignmentFlag.AlignCenter, "OCRMill")

        # Draw status text
        painter.setPen(QPen(QColor(180, 180, 180)))
        font = QFont("Segoe UI", 11)
        painter.setFont(font)
        painter.drawText(0, 410, 400, 25, Qt.AlignmentFlag.AlignCenter, self._status_text)

        # Draw progress bar
        self._draw_progress_bar(painter)

    def _draw_char_ring(self, painter, cx, cy, chars, radius, angle_offset, font_size, is_outer):
        """Draw a ring of characters around the center."""
        font = QFont("Segoe UI", font_size, QFont.Weight.Bold)
        painter.setFont(font)

        num_chars = len(chars)
        for i, char in enumerate(chars):
            angle = math.radians(angle_offset + (i * 360 / num_chars))
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)

            # Alternate colors
            if i % 2 == 0:
                color = self.PURPLE if is_outer else self.TEAL
            else:
                color = self.TEAL if is_outer else self.PURPLE

            # Fade out as they approach center
            alpha = int(255 * (radius / 140))
            color.setAlpha(alpha)

            painter.setPen(QPen(color))
            painter.drawText(int(x) - 10, int(y) - 10, 20, 20,
                           Qt.AlignmentFlag.AlignCenter, char)

    def _draw_arrows(self, painter, cx, cy):
        """Draw spinning circular arrows."""
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._arrow_angle)
        painter.translate(-cx, -cy)

        # Arrow arc parameters
        arrow_radius = 85
        arc_extent = 70  # degrees

        # Top arrow (purple)
        pen = QPen(self.PURPLE, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Draw arcs as approximated paths
        self._draw_arrow_arc(painter, cx, cy, arrow_radius, -35, arc_extent, self.PURPLE)
        self._draw_arrow_arc(painter, cx, cy, arrow_radius, 145, arc_extent, self.PURPLE)
        self._draw_arrow_arc(painter, cx, cy, arrow_radius, 55, arc_extent, self.TEAL)
        self._draw_arrow_arc(painter, cx, cy, arrow_radius, -125, arc_extent, self.TEAL)

        painter.restore()

    def _draw_arrow_arc(self, painter, cx, cy, radius, start_angle, extent, color):
        """Draw an arc with an arrow head."""
        pen = QPen(color, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Draw arc using line segments
        path = QPainterPath()
        start_rad = math.radians(start_angle)

        for i in range(20):
            angle = start_rad + math.radians(extent * i / 19)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        painter.drawPath(path)

        # Arrow head at end
        end_angle = start_rad + math.radians(extent)
        arrow_x = cx + radius * math.cos(end_angle)
        arrow_y = cy + radius * math.sin(end_angle)

        # Draw small triangle for arrow head
        painter.setBrush(QBrush(color))
        arrow_path = QPainterPath()
        head_angle = end_angle + math.radians(90)

        ax1 = arrow_x + 8 * math.cos(head_angle + math.radians(150))
        ay1 = arrow_y + 8 * math.sin(head_angle + math.radians(150))
        ax2 = arrow_x + 8 * math.cos(head_angle - math.radians(150))
        ay2 = arrow_y + 8 * math.sin(head_angle - math.radians(150))

        arrow_path.moveTo(arrow_x, arrow_y)
        arrow_path.lineTo(ax1, ay1)
        arrow_path.lineTo(ax2, ay2)
        arrow_path.closeSubpath()
        painter.drawPath(arrow_path)

    def _draw_mill_wheel(self, painter, cx, cy):
        """Draw the spinning mill wheel."""
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._wheel_angle)
        painter.translate(-cx, -cy)

        # Mill wheel circle with gradient
        gradient = QLinearGradient(cx - 55, cy - 55, cx + 55, cy + 55)
        gradient.setColorAt(0, self.TEAL_LIGHT)
        gradient.setColorAt(1, self.TEAL)

        painter.setPen(QPen(QColor(74, 138, 140), 4))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPoint(cx, cy), 55, 55)

        # Cross spokes
        pen = QPen(QColor(255, 255, 255), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(cx, cy - 45, cx, cy + 45)
        painter.drawLine(cx - 45, cy, cx + 45, cy)

        # Diagonal spokes
        pen = QPen(QColor(255, 255, 255, 150), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        d = 32
        painter.drawLine(cx - d, cy - d, cx + d, cy + d)
        painter.drawLine(cx + d, cy - d, cx - d, cy + d)

        painter.restore()

    def _draw_center_hub(self, painter, cx, cy):
        """Draw the center hub (stationary)."""
        # Hub circle with gradient
        gradient = QLinearGradient(cx - 18, cy - 18, cx + 18, cy + 18)
        gradient.setColorAt(0, self.PURPLE_LIGHT)
        gradient.setColorAt(1, self.PURPLE)

        painter.setPen(QPen(QColor(90, 74, 133), 2))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPoint(cx, cy), 18, 18)

        # White center dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(QPoint(cx, cy), 7, 7)

    def _draw_progress_bar(self, painter):
        """Draw progress bar at bottom."""
        bar_x = 50
        bar_y = 435
        bar_width = 300
        bar_height = 6

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        painter.drawRoundedRect(bar_x, bar_y, bar_width, bar_height, 3, 3)

        # Progress fill
        if self._progress > 0:
            fill_width = int(bar_width * self._progress / 100)
            gradient = QLinearGradient(bar_x, bar_y, bar_x + fill_width, bar_y)
            gradient.setColorAt(0, self.TEAL)
            gradient.setColorAt(1, self.PURPLE)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(bar_x, bar_y, fill_width, bar_height, 3, 3)

    def finish(self):
        """Stop animations and prepare for close."""
        self._wheel_timer.stop()
        self._char_timer.stop()

    def center_on_screen(self):
        """Center the splash screen on the primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(x, y)


class SimpleSplashScreen(QWidget):
    """
    Simpler splash screen with just the spinning wheel.
    For use during quick operations.
    """

    TEAL = QColor(95, 158, 160)
    PURPLE = QColor(107, 91, 149)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(200, 200)

        self._angle = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_angle)
        self._timer.start(30)

    def _update_angle(self):
        self._angle = (self._angle + 4) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 100, 100

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(30, 30, 30, 200)))
        painter.drawEllipse(QPoint(cx, cy), 90, 90)

        # Spinning wheel
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        painter.translate(-cx, -cy)

        # Wheel
        painter.setPen(QPen(QColor(74, 138, 140), 3))
        painter.setBrush(QBrush(self.TEAL))
        painter.drawEllipse(QPoint(cx, cy), 40, 40)

        # Spokes
        pen = QPen(QColor(255, 255, 255), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(cx, cy - 32, cx, cy + 32)
        painter.drawLine(cx - 32, cy, cx + 32, cy)

        painter.restore()

        # Center hub
        painter.setPen(QPen(QColor(90, 74, 133), 2))
        painter.setBrush(QBrush(self.PURPLE))
        painter.drawEllipse(QPoint(cx, cy), 12, 12)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(QPoint(cx, cy), 5, 5)

    def finish(self):
        self._timer.stop()

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(x, y)


# Test code
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    splash = SpinningSplashScreen()
    splash.center_on_screen()
    splash.show()

    # Simulate progress
    progress = [0]
    def update_progress():
        progress[0] += 2
        splash.set_progress(progress[0])
        if progress[0] < 30:
            splash.set_status("Loading configuration...")
        elif progress[0] < 60:
            splash.set_status("Initializing database...")
        elif progress[0] < 90:
            splash.set_status("Loading templates...")
        else:
            splash.set_status("Ready!")

        if progress[0] >= 100:
            timer.stop()
            splash.finish()
            QTimer.singleShot(500, app.quit)

    timer = QTimer()
    timer.timeout.connect(update_progress)
    timer.start(100)

    sys.exit(app.exec())
