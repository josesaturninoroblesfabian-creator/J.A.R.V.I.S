"""Code-drawn companion face, shared by the floating avatar and companion page."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from appearance import PALETTE


def draw_companion(painter, bounds, state, color, seconds, point=(0, 0)):
    painter.save()
    size = min(bounds.width(), bounds.height())
    painter.translate(bounds.center())
    painter.scale(size / 170, size / 170)
    color = QColor(color)
    glow = QRadialGradient(0, 0, 82)
    soft = QColor(color)
    soft.setAlpha(65)
    glow.setColorAt(0, soft)
    glow.setColorAt(1, QColor(0, 0, 0, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(QRectF(-82, -82, 164, 164))
    painter.setBrush(QColor("#101e30"))
    painter.setPen(QPen(color.darker(170), 2))
    painter.drawRoundedRect(QRectF(-64, -49, 128, 98), 31, 31)
    painter.setBrush(QColor("#07121d"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRectF(-56, -41, 112, 80), 24, 24)
    dx, dy = max(-1, min(1, point[0])) * 7, max(-1, min(1, point[1])) * 5
    blink = seconds % 5.4 < 0.13
    height = 3 if blink else 24 + (2 * math.sin(seconds * 3) if state == "listening" else 0)
    painter.setBrush(color)
    for x in [-25, 25]:
        painter.drawRoundedRect(QRectF(x - 11 + dx, -12 - height / 2 + dy, 22, height), 8, 8)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(color, 3, Qt.SolidLine, Qt.RoundCap))
    if state == "speaking":
        opening = 3 + 9 * abs(math.sin(seconds * 12))
        painter.drawEllipse(QRectF(-9, 15 - opening / 2, 18, opening))
    elif state in {"thinking", "tool"}:
        painter.drawLine(QPointF(-6, 20), QPointF(6, 20))
        painter.drawLine(QPointF(-36 + dx, -35), QPointF(-16 + dx, -39))
    elif state == "error":
        painter.drawArc(QRectF(-11, 20, 22, 14), 15 * 16, 150 * 16)
    else:
        smile = QPainterPath(QPointF(-12, 17))
        smile.quadTo(QPointF(0, 29), QPointF(12, 17))
        painter.drawPath(smile)
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QRectF(-3, -64, 6, 6))
    painter.setPen(QPen(color.darker(150), 2))
    painter.drawLine(QPointF(0, -58), QPointF(0, -50))
    painter.restore()


class CompanionFace(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.state, self.point = "idle", None
        self.colors = dict(PALETTE)
        self.setMinimumHeight(145)
        self.setMaximumHeight(165)
        self.setAccessibleName("Cara animada del compañero Jarvis")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(66)

    def set_state(self, state):
        self.state = state

    def paintEvent(self, _event):
        if self.point is None:
            cursor = self.mapFromGlobal(QCursor.pos())
            point = ((cursor.x() - self.width() / 2) / 250, (cursor.y() - self.height() / 2) / 200)
        else:
            point = self.point
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        draw_companion(
            painter,
            QRectF(self.rect()),
            self.state,
            self.colors.get(self.state, self.colors["idle"]),
            time.monotonic(),
            point,
        )
