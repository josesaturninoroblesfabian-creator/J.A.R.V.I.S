#!/usr/bin/env python3
"""J.A.R.V.I.S. — agente nativo de escritorio (Python + PySide6/Qt).

Características:
  * Burbuja cósmica flotante: overlay transparente, siempre visible, arrastrable.
    (clic = abrir/cerrar interfaz · arrastrar = mover · clic derecho = interfaz)
  * Clic en la burbuja: abre la interfaz completa (chat + conexión a apps).
  * Bandeja del sistema: opera en segundo plano.
  * Bucle de voz: escucha -> cerebro configurable -> habla.
  * Acceso real al sistema: ejecuta comandos, lee/escribe archivos, git, web.

Uso:
    cd C:\\Users\\USUARIO\\Desktop\\jarvis\\OpenJarvis
    uv run python C:\\Users\\USUARIO\\Desktop\\jarvis\\jarvis-native\\jarvis_native.py
"""

from __future__ import annotations

import logging
import math
import sys

# ---------------------------------------------------------------------------
# Qt (interfaz nativa)
# ---------------------------------------------------------------------------
from PySide6.QtCore import QObject, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)

from appearance import PALETTE, STATE_LABELS
from brain import JarvisBrain

log = logging.getLogger("jarvis")


class ConfirmationBridge(QObject):
    """Show existing sensitive-tool confirmations on the Qt main thread."""

    requested = Signal(object)

    def __init__(self):
        super().__init__()
        import threading

        self._lock = threading.Lock()
        self._pending = []
        self._dialog = None
        self._closed = False
        self.requested.connect(self._show)

    def confirm(self, prompt):
        import threading

        request = {"prompt": prompt, "event": threading.Event(), "approved": False}
        with self._lock:
            if self._closed:
                return False
            self._pending.append(request)
        self.requested.emit(request)
        request["event"].wait(60)
        with self._lock:
            # A timed-out request must never execute later.
            request["event"].set()
            if request in self._pending:
                self._pending.remove(request)
            return request["approved"]

    @Slot(object)
    def _show(self, request):
        if request["event"].is_set():
            return
        dialog = QMessageBox()
        self._dialog = dialog
        dialog.setWindowTitle("Jarvis · Autorizar herramienta")
        dialog.setText("Jarvis necesita ejecutar esta herramienta para tu petición.")
        dialog.setDetailedText(request["prompt"])
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.setDefaultButton(QMessageBox.No)
        expiry = QTimer(dialog)
        expiry.setSingleShot(True)
        expiry.timeout.connect(dialog.reject)
        expiry.start(60000)
        answer = dialog.exec()
        with self._lock:
            if not request["event"].is_set():
                request["approved"] = answer == QMessageBox.Yes
                request["event"].set()
        self._dialog = None

    def cancel_pending(self):
        with self._lock:
            self._closed = True
            for request in self._pending:
                request["event"].set()
        if self._dialog:
            self._dialog.reject()


def make_icon() -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QRadialGradient(32, 32, 30)
    g.setColorAt(0, QColor(190, 240, 255))
    g.setColorAt(0.55, QColor(60, 120, 235))
    g.setColorAt(1, QColor(12, 22, 70))
    p.setBrush(QBrush(g))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, 60, 60)
    p.end()
    return QIcon(pm)


class CosmicBubble(QWidget):
    """Esfera cósmica flotante: overlay transparente, siempre encima, arrastrable."""

    def __init__(self, brain: JarvisBrain, on_toggle, appearance=None) -> None:
        super().__init__()
        self._brain = brain
        self._on_toggle = on_toggle
        self.appearance = appearance
        self.audio_level = 0
        self.companion_mode = False
        self.gaze_point = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(170, 170)

        self._t = 0.0
        self._drag_offset = None
        self._press_global = None
        self._moved = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(66)

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - 200, geo.bottom() - 210)

    def _tick(self) -> None:
        state = self._brain.status
        self._timer.setInterval(
            33 if state in {"listening", "speaking", "thinking", "tool"} else 80
        )
        self._t += self._timer.interval() / 1000
        self.setToolTip(f"Jarvis · {STATE_LABELS.get(state, 'En espera')} · clic para abrir")
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    # -- pintado -----------------------------------------------------------
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self._brain.status
        base = QColor(
            self.appearance.color(s) if self.appearance else PALETTE.get(s, PALETTE["idle"])
        )
        if self.companion_mode:
            from avatar import draw_companion

            cursor = self.mapFromGlobal(QCursor.pos())
            point = (
                self.gaze_point
                if self.gaze_point is not None
                else (
                    (cursor.x() - self.width() / 2) / 300,
                    (cursor.y() - self.height() / 2) / 250,
                )
            )
            draw_companion(p, QRectF(0, -7, self.width(), self.height()), s, base, self._t, point)
            p.setPen(base.lighter(130))
            p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
            p.drawText(
                QRectF(0, 146, self.width(), 20),
                Qt.AlignCenter,
                STATE_LABELS.get(s, "Aquí contigo"),
            )
            p.end()
            return

        def tint(alpha=255, light=100):
            color = base.lighter(light)
            color.setAlpha(alpha)
            return color

        cx, cy = self.width() / 2, self.height() / 2
        R = 52.0

        if s == "listening":
            scale = 1 + 0.04 * math.sin(self._t * 6) + min(self.audio_level, 100) / 600
        elif s == "thinking":
            scale = 1 + 0.09 * math.sin(self._t * 9)
        elif s == "speaking":
            scale = 1 + 0.07 * math.sin(self._t * 7)
        elif s in {"boot", "voice"}:
            scale = 1 + 0.05 * math.sin(self._t * 2)
        else:
            scale = 1 + 0.03 * math.sin(self._t * 1.4)
        R *= scale

        # halo exterior
        glow = QRadialGradient(cx, cy, R * 1.9)
        glow.setColorAt(0, tint(95 if s == "thinking" else 70))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - R * 1.9, cy - R * 1.9, R * 3.8, R * 3.8))

        # cuerpo de la esfera
        body = QRadialGradient(cx - R * 0.3, cy - R * 0.3, R * 0.1, cx, cy, R)
        body.setColorAt(0, tint(235, 155))
        body.setColorAt(0.5, tint(215, 90))
        body.setColorAt(1, tint(165, 35))
        p.setBrush(QBrush(body))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - R, cy - R, R * 2, R * 2))

        # arcos de energía giratorios
        p.save()
        p.translate(cx, cy)
        p.rotate(self._t * (28 if s == "thinking" else 8))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(tint(150, 140), 2))
        p.drawArc(QRectF(-R * 0.72, -R * 0.72, R * 1.44, R * 1.44), 0, 100 * 16)
        p.setPen(QPen(tint(110, 125), 1.5))
        p.drawArc(QRectF(-R * 0.5, -R * 0.5, R * 1.0, R * 1.0), 130 * 16, 90 * 16)
        p.restore()

        # núcleo brillante
        core = QRadialGradient(cx, cy, 0, cx, cy, R * 0.35)
        core.setColorAt(0, QColor(255, 255, 255, 225))
        core.setColorAt(0.5, tint(140, 160))
        core.setColorAt(1, tint(0))
        p.setBrush(QBrush(core))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - R * 0.35, cy - R * 0.35, R * 0.7, R * 0.7))

        # ondas al hablar
        if s == "speaking":
            for i in range(3):
                ph = (self._t * 0.9 + i / 3) % 1.0
                rr = R + ph * R * 1.5
                p.setPen(QPen(tint(int((1 - ph) * 130)), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # partículas orbitales
        speed = 1.6 if s == "thinking" else 0.55
        for i in range(36):
            a = self._t * speed + i * (2 * math.pi / 36)
            rr = R * 1.35
            px = cx + math.cos(a) * rr
            py = cy + math.sin(a) * rr * 0.6
            depth = (math.sin(a) + 1) / 2
            c = tint(int(40 + depth * 150), 135)
            p.setBrush(QBrush(c))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(px - 1.5, py - 1.5, 3, 3))

        p.setPen(tint(230, 145))
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(
            QRectF(5, 145, 160, 20), Qt.AlignCenter, STATE_LABELS.get(s, "En espera").upper()
        )
        p.end()

    # -- interacción -------------------------------------------------------
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._press_global = e.globalPosition().toPoint()
            self._moved = False

    def mouseMoveEvent(self, e) -> None:
        if self._drag_offset is not None:
            g = e.globalPosition().toPoint()
            if self._press_global is not None and (g - self._press_global).manhattanLength() > 5:
                self._moved = True
            self.move(g - self._drag_offset)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.LeftButton and not self._moved:
            self._on_toggle()
        self._drag_offset = None


def main() -> None:
    if "--self-test" in sys.argv:
        from diagnostics import run

        report = sys.argv[sys.argv.index("--self-test") + 1]
        raise SystemExit(run(report))

    from desktop import DATA_DIR, DesktopController
    from profiles import load_settings
    from runtime_support import SingleInstance

    app = QApplication(sys.argv)
    app.setApplicationName("J.A.R.V.I.S.")
    app.setOrganizationName("JarvisPersonal")
    app.setQuitOnLastWindowClosed(False)
    instance = SingleInstance(DATA_DIR)
    if not instance.acquire():
        return
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler

    logging.basicConfig(
        handlers=[
            RotatingFileHandler(
                log_dir / "jarvis_native.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8"
            )
        ],
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    bridge = ConfirmationBridge()
    try:
        settings = load_settings()
        controller = DesktopController(bridge, settings)
        if "--no-greeting" in sys.argv:
            controller._greeted = True
    except Exception as exc:
        log.exception("No se pudo crear la aplicación")
        QMessageBox.critical(None, "Jarvis", f"No se pudo iniciar Jarvis: {exc}")
        instance.close()
        return

    def show_window():
        if controller.closing:
            return
        controller.window.showNormal()
        controller.window.raise_()
        controller.window.activateWindow()

    instance.show_requested.connect(show_window)
    bubble = CosmicBubble(
        controller.brain or type("Status", (), {"status": "boot"})(),
        show_window,
        appearance=controller.appearance,
    )
    bubble.companion_mode = controller.companion.focus.settings.avatar
    controller.companion.avatar_changed.connect(
        lambda enabled: setattr(bubble, "companion_mode", enabled)
    )
    controller.companion.gaze_changed.connect(lambda point: setattr(bubble, "gaze_point", point))
    controller.window.level.valueChanged.connect(
        lambda level: setattr(bubble, "audio_level", level)
    )
    bubble.setToolTip("Jarvis · clic para abrir tu conversación")

    def update_bubble(state):
        if controller.brain is not None:
            bubble._brain = controller.brain
        bubble._brain.status = state if state in PALETTE else "idle"

    controller.state_changed.connect(update_bubble)
    tray = QSystemTrayIcon(make_icon(), app)
    tray.setToolTip("J.A.R.V.I.S. · Una sesión de texto y voz")
    menu = QMenu()
    open_action = menu.addAction("Abrir Jarvis")
    open_action.triggered.connect(show_window)
    voice_action = menu.addAction("Probar voz en español")
    voice_action.triggered.connect(controller.test_voice)
    listen_action = menu.addAction("Hablar ahora")
    listen_action.triggered.connect(controller.listen_once)
    hologram_action = menu.addAction("Mostrar holograma")
    hologram_action.setCheckable(True)
    hologram_action.setChecked(controller.window.show_hologram.isChecked())

    def show_hologram(visible):
        controller.window.preferences.setValue("hologram_visible", visible)
        hologram_action.setChecked(visible)
        bubble.setVisible(visible and not controller.closing)

    controller.window.show_hologram.toggled.connect(show_hologram)
    hologram_action.toggled.connect(controller.window.show_hologram.setChecked)
    menu.addSeparator()
    quit_action = menu.addAction("Salir de Jarvis")
    quit_action.triggered.connect(controller.shutdown)
    tray.setContextMenu(menu)
    bubble.setContextMenuPolicy(Qt.CustomContextMenu)
    bubble.customContextMenuRequested.connect(lambda point: menu.popup(bubble.mapToGlobal(point)))
    tray.activated.connect(
        lambda reason: show_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
    )
    tray.show()
    controller.companion.notification.connect(
        lambda text: (
            tray.showMessage("Jarvis · Aquí contigo", text, QSystemTrayIcon.Information, 6000)
            if not controller.window.isVisible()
            else None
        )
    )

    def hide_desktop():
        menu.close()
        tray.hide()
        bubble.hide()

    def finish():
        instance.close()
        hide_desktop()
        app.quit()

    controller.closing_started.connect(hide_desktop)
    controller.stopped.connect(finish)
    app.setWindowIcon(make_icon())
    controller.window.setWindowIcon(make_icon())
    available = app.primaryScreen().availableGeometry()
    controller.window.resize(min(1320, available.width() - 50), min(840, available.height() - 50))
    show_hologram(controller.window.show_hologram.isChecked())
    if "--background" not in sys.argv:
        show_window()
    app.exec()
    instance.close()


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
