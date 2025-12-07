from __future__ import annotations

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtWidgets import QWidget


class RecordingIcon(QWidget):
    """
    Анимированная иконка записи — пульсирующая красная точка.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius_multiplier = 1.0

        self.animation = QPropertyAnimation(self, b"radiusMultiplier")
        self.animation.setDuration(800)
        self.animation.setStartValue(0.8)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.setLoopCount(-1)
        self.animation.start()

    @pyqtProperty(float)
    def radiusMultiplier(self) -> float:
        return self._radius_multiplier

    @radiusMultiplier.setter
    def radiusMultiplier(self, value: float) -> None:
        self._radius_multiplier = value
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x, center_y = self.width() / 2, self.height() / 2
        base_radius = min(center_x, center_y) * 0.6
        radius = base_radius * self._radius_multiplier

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#FF3B30")))
        painter.drawEllipse(int(center_x - radius), int(center_y - radius), int(radius * 2), int(radius * 2))


class ProcessingIcon(QWidget):
    """
    Анимированная иконка обработки — вращающийся спиннер.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_angle)
        self.timer.start(30)  # ~33 FPS

    def _update_angle(self) -> None:
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x, center_y = self.width() / 2, self.height() / 2
        radius = min(center_x, center_y) * 0.7
        pen_width = max(2.0, radius * 0.15)

        pen = QPen(QColor("#007AFF"), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Рисуем дугу
        start_angle = self._angle * 16
        span_angle = 270 * 16
        painter.drawArc(
            int(center_x - radius),
            int(center_y - radius),
            int(radius * 2),
            int(radius * 2),
            start_angle,
            span_angle,
        )


class ReadyIcon(QWidget):
    """
    Статичная иконка готовности — зеленая галочка.
    """

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x, center_y = self.width() / 2, self.height() / 2
        size = min(center_x, center_y) * 1.2
        pen_width = max(2.0, size * 0.15)

        pen = QPen(QColor("#34C759"), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # Рисуем галочку
        points = [
            (center_x - size * 0.4, center_y),
            (center_x - size * 0.1, center_y + size * 0.3),
            (center_x + size * 0.4, center_y - size * 0.2),
        ]
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i+1]
            painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
