"""KFlow — Widget de vista previa interactiva del layout de mosaico (HU-05)."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from tiling_preview import compute_layout

ACCENT_COLORS = [
    "#3DAEE9", "#27AE60", "#E67E22", "#9B59B6",
    "#E74C3C", "#1ABC9C", "#F1C40F", "#95A5A6",
    "#EC407A", "#7F8C8D", "#2ECC71", "#5DADE2",
]

VIRTUAL_SCREEN_SIZE = (1920, 1080)


class TilingPreviewWidget(QWidget):
    """Dibuja el resultado de tiling_preview.compute_layout a escala del widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 200)
        self._inner_gap = 8
        self._outer_margins = {"top": 24, "bottom": 8, "left": 8, "right": 8}
        self._window_count = 4

    def set_inner_gap(self, value):
        self._inner_gap = value
        self.update()

    def set_outer_margins(self, top, bottom, left, right):
        self._outer_margins = {"top": top, "bottom": bottom, "left": left, "right": right}
        self.update()

    def set_window_count(self, count):
        self._window_count = max(0, count)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1B1E20"))

        virtual_w, virtual_h = VIRTUAL_SCREEN_SIZE
        scale = min(self.width() / virtual_w, self.height() / virtual_h)
        offset_x = (self.width() - virtual_w * scale) / 2
        offset_y = (self.height() - virtual_h * scale) / 2

        area = {"x": 0, "y": 0, "width": virtual_w, "height": virtual_h}
        rects = compute_layout(area, self._inner_gap, self._outer_margins, self._window_count)

        for i, rect in enumerate(rects):
            color = QColor(ACCENT_COLORS[i % len(ACCENT_COLORS)])
            painter.setPen(QPen(color.darker(140), 2))
            painter.setBrush(color.darker(220))
            x = offset_x + rect["x"] * scale
            y = offset_y + rect["y"] * scale
            w = rect["width"] * scale
            h = rect["height"] * scale
            painter.drawRoundedRect(int(x), int(y), int(w), int(h), 6, 6)

        painter.end()
