"""One Spanish desktop, one brain, and one serialized conversation for text/voice."""

from __future__ import annotations

import html
import json
import logging
import re
import threading
import time

from PySide6.QtCore import QObject, QSettings, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app_paths import data_dir
from brain import JarvisBrain
from profiles import PROFILE_PATH, load_settings
from ui_style import STYLE
from voice import record_speech

log = logging.getLogger("jarvis")

DATA_DIR = data_dir()


def spoken_reply(text):
    """Read the visible wording of a reply without Markdown or code blocks."""
    text = re.sub(r"<think>.*?(?:</think>|\Z)", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(
        r"(?ms)^ {0,3}(```|~~~)[^\n]*\n.*?(?:^ {0,3}\1[ \t]*$|\Z)",
        "\nEl código está en la conversación.\n",
        text,
    )
    document = QTextDocument()
    document.setMarkdown(text, QTextDocument.MarkdownDialectGitHub | QTextDocument.MarkdownNoHTML)
    plain = re.sub(r"https?://\S+", "", document.toPlainText())
    return " ".join(plain.split())


STATES = {
    "boot": "Preparando el cerebro…",
    "voice": "Preparando la voz…",
    "idle": "Listo para ayudarte",
    "listening": "Escuchando · di «Jarvis»",
    "thinking": "Pensando…",
    "speaking": "Hablando…",
    "error": "Necesita atención",
    "tool": "Usando una herramienta…",
    "transcribing": "Reconociendo tu voz…",
    "paused": "En pausa",
}


class Job(QThread):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            self.result.emit(self.operation())
        except Exception as exc:
            log.exception("Falló una operación del escritorio")
            self.error.emit(str(exc))


class StartupJob(Job):
    state = Signal(str)

    def __init__(self, brain, parent=None):
        super().__init__(lambda: brain.init(self.state.emit, initialize_voice=False), parent)


def wake_command(text, *, require_wake=True):
    """Allow common Spanish transcriptions; a single listen bypasses wake words."""
    if not require_wake:
        return text.strip()
    match = re.search(
        r"\b(?:jarvis|yarvis|jarbis|yarbis|yervis|carbis|carvis|harvis)\b[,:!.]?\s*",
        text,
        re.I,
    )
    if not match:
        return None
    return (text[: match.start()] + text[match.end() :]).strip(" ,.!?¿¡")


class ListenJob(QThread):
    heard = Signal(str)
    command = Signal(str)
    state = Signal(str)
    level = Signal(int)
    error = Signal(str)

    def __init__(
        self, brain, *, device=None, threshold=250, once=False, require_wake=True, followup_until=0
    ):
        super().__init__()
        self.brain, self.device, self.threshold = brain, device, threshold
        self.once, self.require_wake = once, require_wake
        self.cancelled = threading.Event()
        self.followup_until = followup_until

    def stop(self):
        self.cancelled.set()

    def run(self):
        wake_until = self.followup_until
        try:
            while not self.cancelled.is_set():
                self.state.emit("Habla ahora…" if self.once else STATES["listening"])
                wav = record_speech(
                    self.cancelled,
                    device=self.device,
                    threshold=self.threshold,
                    on_level=self.level.emit,
                )
                self.level.emit(0)
                if self.cancelled.is_set():
                    return
                if not wav:
                    if self.once:
                        self.state.emit("No detecté voz. Revisa el micrófono o la sensibilidad.")
                        return
                    continue
                self.state.emit("Reconociendo lo que dijiste…")
                text = self.brain.transcribe(wav)
                if self.cancelled.is_set():
                    return
                if not text:
                    if self.once:
                        self.state.emit("No pude entender el audio. Prueba de nuevo.")
                        return
                    continue
                self.heard.emit(text)
                command = wake_command(
                    text,
                    require_wake=self.require_wake
                    and not self.once
                    and time.monotonic() > wake_until,
                )
                if command is None:
                    self.state.emit("Te oí. Di «Jarvis» o pulsa «Hablar ahora».")
                    continue
                if not command:
                    wake_until = time.monotonic() + 12
                    self.state.emit("Te escucho. Dime qué necesitas.")
                    continue
                self.command.emit(command)
                return
        except Exception as exc:
            log.exception("Error de escucha")
            self.error.emit(f"Micrófono o reconocimiento de voz: {exc}")


def label(text, *, name=None, wrap=True):
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    result.setWordWrap(wrap)
    return result


class JarvisWindow(QMainWindow):
    submit = Signal(str)
    listen = Signal()
    test_voice = Signal()
    reconnect = Signal(str)
    pause_voice = Signal()
    new_conversation = Signal()
    select_conversation = Signal(str)
    stop_requested = Signal()
    exit_requested = Signal()
    credential_save = Signal(str)
    performance_changed = Signal()

    def __init__(self, settings):
        super().__init__()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.preferences = QSettings(str(DATA_DIR / "preferences.ini"), QSettings.IniFormat)
        self.setWindowTitle("J.A.R.V.I.S. · Asistente personal")
        self.resize(1320, 840)
        self.setMinimumSize(980, 680)
        self._messages = []
        self._partial = ""
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self.render_conversation)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(17, 22, 17, 18)
        side.addWidget(label("J.A.R.V.I.S.", name="brand"))
        side.addWidget(label("ASISTENTE PERSONAL · ESPAÑOL", name="muted"))
        side.addSpacing(16)
        new_chat = QPushButton("＋  Nueva conversación")
        new_chat.clicked.connect(self.new_conversation.emit)
        side.addWidget(new_chat)
        side.addSpacing(8)
        self.nav_layout = QVBoxLayout()
        self.nav_layout.setSpacing(5)
        side.addLayout(self.nav_layout)
        self.stack = QStackedWidget()
        self.nav = []
        for index, text in enumerate(
            ["Conversación", "Voz y micrófono", "Cerebro", "Estado y herramientas"]
        ):
            button = QPushButton(text)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, index=index: self.show_page(index))
            self.nav_layout.addWidget(button)
            self.nav.append(button)
        side.addSpacing(15)
        side.addWidget(label("CONVERSACIONES GUARDADAS", name="muted"))
        self.sessions = QListWidget()
        self.sessions.setMinimumHeight(75)
        self.sessions.currentItemChanged.connect(
            lambda item, _previous: self.select_conversation.emit(item.data(256)) if item else None
        )
        side.addWidget(self.sessions, 1)
        self.show_hologram = QCheckBox("Mostrar holograma")
        self.show_hologram.setChecked(self.preferences.value("hologram_visible", True, type=bool))
        side.addWidget(self.show_hologram)
        self.exit_button = QPushButton("Salir de Jarvis")
        self.exit_button.setToolTip("Cierra Jarvis y su holograma")
        self.exit_button.clicked.connect(self.close)
        side.addWidget(self.exit_button)
        layout.addWidget(sidebar)
        body = QVBoxLayout()
        body.setContentsMargins(26, 23, 24, 20)
        header = QHBoxLayout()
        self.title = label("Conversación", name="title")
        self.model_chip = label("Conectando…", name="modelChip")
        self.model_chip.setWordWrap(False)
        header.addWidget(self.title, 1)
        header.addWidget(self.model_chip)
        self.activity_toggle = QCheckBox("Actividad")
        self.activity_toggle.setChecked(True)
        header.addWidget(self.activity_toggle)
        self.status = label("Preparando el cerebro…", name="status")
        body.addLayout(header)
        body.addWidget(self.status)
        body.addSpacing(8)
        workspace = QHBoxLayout()
        workspace.setSpacing(18)
        workspace.addWidget(self.stack, 1)
        self.activity_card = QFrame()
        self.activity_card.setObjectName("activityCard")
        self.activity_card.setFixedWidth(235)
        activity_box = QVBoxLayout(self.activity_card)
        activity_box.setContentsMargins(16, 18, 16, 16)
        activity_box.addWidget(label("ACTIVIDAD EN TIEMPO REAL", name="muted"))
        self.latency = label("Sin peticiones todavía", name="muted")
        activity_box.addWidget(self.latency)
        self.activity = QTextBrowser()
        self.activity.setStyleSheet("border:0;padding:0;background:transparent")
        activity_box.addWidget(self.activity, 1)
        activity_box.addWidget(label("ESTADOS DEL HOLOGRAMA", name="muted"))
        from appearance import PALETTE, STATE_LABELS

        self.state_legend = {}
        for state in ["listening", "thinking", "tool", "speaking", "error"]:
            item = QLabel(f'<span style="color:{PALETTE[state]}">●</span>  {STATE_LABELS[state]}')
            self.state_legend[state] = item
            activity_box.addWidget(item)
        self.stop_button = QPushButton("■  Detener")
        self.stop_button.setObjectName("danger")
        self.stop_button.clicked.connect(self.stop_requested.emit)
        activity_box.addWidget(self.stop_button)
        workspace.addWidget(self.activity_card)
        self.activity_toggle.toggled.connect(self.activity_card.setVisible)
        body.addLayout(workspace, 1)
        layout.addLayout(body, 1)
        self._chat_page()
        self._voice_page(settings)
        self._model_page(settings)
        self._status_page()
        from ui_panels import WorkspacePanels

        self.panels = WorkspacePanels(self)
        from companion_panel import CompanionPanel

        self.companion_panel = CompanionPanel(self, self.panels.page)
        self.show_page(0)

    def show_page(self, index):
        self.stack.setCurrentIndex(index)
        self.title.setText(self.nav[index].text())
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)

    def update_palette(self, colors):
        from appearance import STATE_LABELS

        self.panels.update_palette(colors)
        self.companion_panel.face.colors = dict(colors)
        for state, item in self.state_legend.items():
            item.setText(f'<span style="color:{colors[state]}">●</span>  {STATE_LABELS[state]}')

    def _chat_page(self):
        page, box = QWidget(), QVBoxLayout()
        page.setLayout(box)
        box.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        toolbar.addWidget(label("TU ESPACIO DE TRABAJO", name="muted"), 1)
        copy = QPushButton("Copiar respuesta")
        copy.clicked.connect(self.copy_last_answer)
        toolbar.addWidget(copy)
        box.addLayout(toolbar)
        self.conversation = QTextBrowser()
        self.conversation.setAccessibleName("Historial de la conversación")
        self.conversation.setOpenExternalLinks(False)
        self.conversation.document().setDefaultStyleSheet(
            "body{color:#dce5f3;font-size:14px;}p{line-height:1.6}"
            "pre{background:#0a1220;padding:12px;color:#9de6de;}"
            "code{color:#a3e0ed;}h1,h2,h3{color:#f0f5ff}"
            "table{border-collapse:collapse}td,th{border:1px solid #354359;padding:6px}"
        )
        box.addWidget(self.conversation, 1)
        suggestions = QHBoxLayout()
        for text, prompt in [
            ("Cambiar holograma", "Cambia el holograma a morado"),
            ("Ver mi pantalla", "Mira mi pantalla y describe qué ves"),
            ("Ayuda con código", "Ayúdame a revisar un proyecto de programación"),
        ]:
            button = QPushButton(text)
            button.clicked.connect(
                lambda _checked=False, prompt=prompt: self.input.setPlainText(prompt)
            )
            suggestions.addWidget(button)
        box.addLayout(suggestions)
        self.heard = label("Micrófono: esperando a que termine el inicio.", name="muted")
        box.addWidget(self.heard)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("Escribe lo que necesitas. Por ejemplo: calcula 137 × 29.")
        self.input.setAccessibleName("Mensaje para Jarvis")
        self.input.setMaximumHeight(92)
        self.send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input)
        self.send_shortcut.activated.connect(self._send)
        box.addWidget(self.input)
        row = QHBoxLayout()
        self.listen_button = QPushButton("Hablar ahora")
        self.listen_button.clicked.connect(self.listen.emit)
        row.addWidget(self.listen_button)
        self.read_replies = QCheckBox("Leer respuestas en voz alta")
        self.read_replies.setChecked(self.preferences.value("read_replies", True, type=bool))
        self.read_replies.toggled.connect(lambda on: self.preferences.setValue("read_replies", on))
        row.addWidget(self.read_replies)
        row.addStretch()
        self.send = QPushButton("Enviar  ↑")
        self.send.setObjectName("primary")
        self.send.clicked.connect(self._send)
        row.addWidget(self.send)
        box.addLayout(row)
        self.stack.addWidget(page)
        self.set_busy(True)

    def _send(self):
        text = self.input.toPlainText().strip()
        if text:
            self.submit.emit(text)

    def _voice_page(self, settings):
        page, box = QWidget(), QVBoxLayout()
        page.setLayout(box)
        box.addWidget(label("Escucha y respuesta hablada", name="title"))
        box.addWidget(
            label(
                "«Hablar ahora» escucha una petición sin exigir la palabra Jarvis. "
                "La escucha continua espera «Jarvis» antes de responder.",
                name="muted",
            )
        )
        self.voice_status = label("Preparando reconocimiento y voz…")
        box.addWidget(self.voice_status)
        form = QFormLayout()
        self.voice_mode = QComboBox()
        self.voice_mode.addItem("Ligero · voz de Windows + reconocimiento local compacto", "light")
        from app_paths import FROZEN

        if not FROZEN:
            self.voice_mode.addItem("Calidad local avanzada · consume más memoria y CPU", "neural")
        self.voice_mode.setCurrentIndex(max(0, self.voice_mode.findData(settings.voice_mode)))
        form.addRow("Modo de voz", self.voice_mode)
        self.microphone, self.speaker = QComboBox(), QComboBox()
        self.microphone.addItem("Micrófono predeterminado", None)
        self.speaker.addItem("Altavoces predeterminados", None)
        try:
            import sounddevice as sd

            for i, device in enumerate(sd.query_devices()):
                if device["max_input_channels"]:
                    self.microphone.addItem(f"{device['name']} · {i}", i)
                if device["max_output_channels"]:
                    self.speaker.addItem(f"{device['name']} · {i}", i)
        except Exception as exc:
            self.voice_status.setText(f"No pude consultar los dispositivos: {exc}")
        for name, combo in [("microphone", self.microphone), ("speaker", self.speaker)]:
            stored = self.preferences.value(name, -1, type=int)
            index = combo.findData(stored)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(
                lambda _index, name=name, combo=combo: self._device_changed(name, combo)
            )
        form.addRow("Micrófono", self.microphone)
        form.addRow("Salida de sonido", self.speaker)
        self.threshold = QSpinBox()
        self.threshold.setRange(50, 3000)
        self.threshold.setSingleStep(50)
        self.threshold.setValue(self.preferences.value("threshold", 250, type=int))
        self.threshold.valueChanged.connect(
            lambda value: self.preferences.setValue("threshold", value)
        )
        form.addRow("Umbral de voz (menor = más sensible)", self.threshold)
        box.addLayout(form)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        box.addWidget(label("Nivel del micrófono", name="muted"))
        box.addWidget(self.level)
        self.continuous = QCheckBox("Escuchar en segundo plano")
        self.continuous.setChecked(self.preferences.value("continuous", True, type=bool))
        self.continuous.toggled.connect(self._continuous_changed)
        box.addWidget(self.continuous)
        self.require_wake = QCheckBox("Activar con la palabra «Jarvis»")
        self.require_wake.setChecked(self.preferences.value("require_wake", True, type=bool))
        self.require_wake.toggled.connect(lambda on: self.preferences.setValue("require_wake", on))
        box.addWidget(self.require_wake)
        self.test_button = QPushButton("Probar voz en español")
        self.test_button.clicked.connect(self.test_voice.emit)
        box.addWidget(self.test_button)
        box.addWidget(
            label(
                "Si la barra no se mueve al hablar, selecciona otro micrófono. Si "
                "oyes una respuesta pero no se entiende, ajusta la salida de "
                "sonido.",
                name="muted",
            )
        )
        box.addStretch()
        self.stack.addWidget(page)

    def _device_changed(self, name, combo):
        self.preferences.setValue(
            name, combo.currentData() if combo.currentData() is not None else -1
        )
        if name == "microphone":
            self.pause_voice.emit()

    def _continuous_changed(self, on):
        self.preferences.setValue("continuous", on)
        self.pause_voice.emit()

    def _model_page(self, settings):
        page, box = QWidget(), QVBoxLayout()
        page.setLayout(box)
        box.addWidget(label("Elige el cerebro", name="title"))
        box.addWidget(
            label(
                "Los modelos locales funcionan en tu equipo. Las APIs necesitan una "
                "clave configurada; no se activa ningún servicio de pago "
                "automáticamente.",
                name="muted",
            )
        )
        self.model = QComboBox()
        for name, profile in settings.profiles.items():
            self.model.addItem(profile.label, name)
        self.model.setCurrentIndex(self.model.findData(settings.profile.name))
        box.addWidget(self.model)
        self.local_vision = QCheckBox(
            "Permitir análisis visual con IA local (requiere Ollama y más recursos)"
        )
        self.local_vision.setChecked(settings.allow_local_vision)
        box.addWidget(self.local_vision)
        self.apply_model = QPushButton("Aplicar y reconectar")
        self.apply_model.setObjectName("primary")
        self.apply_model.clicked.connect(self.performance_changed.emit)
        box.addWidget(self.apply_model)
        self.model_status = label("Preparando el modelo…")
        box.addWidget(self.model_status)
        box.addWidget(
            label(
                "Modo ligero: cerebro en Groq y voz local compacta. La cámara del compañero "
                "funciona sin IA visual pesada ni envíos de imagen a Groq.",
                name="muted",
            )
        )
        self.groq_key = QLineEdit()
        self.groq_key.setEchoMode(QLineEdit.Password)
        self.groq_key.setPlaceholderText("Nueva clave de Groq · guardada cifrada para tu usuario")
        self.groq_key.setAccessibleName("Clave API de Groq")
        box.addWidget(self.groq_key)
        save_key = QPushButton("Guardar y comprobar Groq")

        def submit_key():
            key = self.groq_key.text().strip()
            self.groq_key.clear()
            self.credential_save.emit(key)

        save_key.clicked.connect(submit_key)
        box.addWidget(save_key)
        self.credential_status = label(
            "Puedes utilizar una clave guardada o configurar una nueva.", name="muted"
        )
        box.addWidget(self.credential_status)
        box.addWidget(
            label(
                "Local rápido: menor consumo y espera. Local completo: compara su "
                "calidad en tareas complejas. Cambiar de cerebro conserva la "
                "conversación.",
                name="muted",
            )
        )
        box.addStretch()
        self.stack.addWidget(page)

    def _status_page(self):
        page, box = QWidget(), QVBoxLayout()
        page.setLayout(box)
        box.addWidget(label("Estado real de Jarvis", name="title"))
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        box.addWidget(self.diagnostics)
        self.tool_list = QListWidget()
        self.tool_list.setMaximumHeight(170)
        self.tool_list.currentItemChanged.connect(self._tool_selected)
        box.addWidget(self.tool_list)
        self.tool_details = label("Selecciona una herramienta para ver su función.", name="muted")
        box.addWidget(self.tool_details)
        self.retry = QPushButton("Reconectar y volver a preparar la voz")
        self.retry.clicked.connect(lambda: self.reconnect.emit(self.model.currentData()))
        box.addWidget(self.retry)
        files = QPushButton("Abrir carpeta de datos y preferencias")
        files.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR))))
        box.addWidget(files)
        box.addWidget(
            label(
                "El historial y la voz usan el mismo cerebro. Las herramientas "
                "mostradas aquí son las cargadas en esta sesión.",
                name="muted",
            )
        )
        self.stack.addWidget(page)

    def append_message(self, role, text):
        self._partial = ""
        self._messages.append((role, text))
        self.render_conversation()

    def stream_text(self, text):
        self._partial = text
        if not self._render_timer.isActive():
            self._render_timer.start(75)

    def render_conversation(self):
        messages = self._messages + ([("assistant", self._partial)] if self._partial else [])
        blocks = []
        for role, text in messages:
            document = QTextDocument()
            document.setMarkdown(html.escape(text))
            rich = document.toHtml().split("<body", 1)[-1].split(">", 1)[-1].rsplit("</body>", 1)[0]
            name, color = ("TÚ", "#a8b8cf") if role == "user" else ("JARVIS", "#8cdeee")
            blocks.append(
                f'<p style="color:{color};font-size:11px;margin-top:24px"><b>{name}</b></p>'
                f'<div style="margin-bottom:22px">{rich}</div>'
            )
        self.conversation.setHtml("".join(blocks))
        self.conversation.moveCursor(QTextCursor.End)

    def reset_messages(self, rows):
        self._messages = list(rows)
        self._partial = ""
        self.render_conversation()

    def copy_last_answer(self):
        from PySide6.QtWidgets import QApplication

        for role, text in reversed(self._messages):
            if role == "assistant":
                QApplication.clipboard().setText(text)
                return

    def add_activity(self, text):
        self.activity.append(
            f'<p><span style="color:#7289a8">{time.strftime("%H:%M:%S")}</span><br>'
            f"{html.escape(text)}</p>"
        )

    def _tool_selected(self, item, _previous):
        if item:
            self.tool_details.setText(item.data(256))

    def set_busy(self, busy):
        self.send.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.listen_button.setEnabled(not busy)
        self.sessions.setEnabled(not busy)
        if hasattr(self, "apply_model"):
            self.apply_model.setEnabled(not busy)
            self.retry.setEnabled(not busy)

    def closeEvent(self, event):
        event.ignore()
        self.exit_requested.emit()


class DesktopController(QObject):
    state_changed = Signal(str)
    stopped = Signal()
    closing_started = Signal()
    appearance_changed = Signal()
    tool_event = Signal(object)
    partial_text = Signal(str)
    scheduled_result = Signal(object)

    def __init__(self, bridge, settings):
        super().__init__()
        self.bridge, self.settings = bridge, settings
        self.brain = None
        self.window = JarvisWindow(settings)
        self.window.submit.connect(self.submit)
        self.window.listen.connect(self.listen_once)
        self.window.test_voice.connect(self.test_voice)
        self.window.reconnect.connect(self.connect_brain)
        self.window.pause_voice.connect(self.restart_listening)
        from appearance import AppearanceStore
        from native_tools import DesktopAccess

        self.appearance = AppearanceStore(DATA_DIR / "hologram.json", self.appearance_changed.emit)
        self.desktop_access = DesktopAccess()
        self.appearance_changed.connect(
            lambda: self.window.update_palette(self.appearance.colors())
        )
        self.window.update_palette(self.appearance.colors())
        self.tool_event.connect(self._tool_event)
        self.partial_text.connect(self.window.stream_text)
        self.window.new_conversation.connect(self.new_conversation)
        self.window.select_conversation.connect(self.select_conversation)
        self.window.stop_requested.connect(self.stop_current)
        self.window.exit_requested.connect(self.shutdown)
        panels = self.window.panels
        panels.palette_set.connect(lambda state, color: self.appearance.set(state, color))
        panels.desktop_enabled.connect(self.set_desktop_enabled)
        panels.desktop_test.connect(self.test_desktop)
        panels.memory_save.connect(self.save_memory)
        panels.memory_search.connect(self.search_memory)
        panels.schedule_create.connect(self.create_schedule)
        panels.schedule_toggle.connect(self.toggle_schedule)
        panels.schedule_refresh.connect(self.refresh_schedules)
        self.schedules = None
        self.scheduled_result.connect(self.on_scheduled_result)
        self._request_started = None
        self.jobs = set()
        self.listener = None
        self.busy = self.closing = self.voice_loading = False
        self._speech_blocked = False
        self._loaded_history = False
        self._greeted = False
        self._followup_until = 0
        from companion_runtime import CompanionRuntime

        self.companion = CompanionRuntime(self, DATA_DIR)
        self.window.credential_save.connect(self.save_groq_credential)
        self.window.performance_changed.connect(self.apply_performance)
        self.window.voice_mode.currentIndexChanged.connect(self.apply_performance)
        self.shutdown_timer = QTimer(self)
        self.shutdown_timer.timeout.connect(self._finish_shutdown)
        self.connect_brain(settings.profile.name)

    def _track(self, job):
        self.jobs.add(job)
        job.finished.connect(lambda job=job: self._forget(job))
        job.start()

    @Slot()
    def apply_performance(self):
        if self.busy or self.voice_loading or self.closing:
            return
        import tomlkit

        doc = tomlkit.parse(PROFILE_PATH.read_text(encoding="utf-8"))
        doc["voice_mode"] = self.window.voice_mode.currentData()
        doc["allow_local_vision"] = self.window.local_vision.isChecked()
        temporary = PROFILE_PATH.with_suffix(".tmp")
        temporary.write_text(tomlkit.dumps(doc), encoding="utf-8")
        temporary.replace(PROFILE_PATH)
        self.connect_brain(self.window.model.currentData())

    @Slot(str)
    def save_groq_credential(self, key):
        if self.busy or self.closing:
            self.window.credential_status.setText("Espera a que termine la operación actual.")
            return
        from credential_store import CredentialStore, credential_error
        from providers import GroqEngine

        def check():
            engine = None
            try:
                store = CredentialStore()
                if key:
                    store.save("GROQ_API_KEY", key)
                engine = GroqEngine(api_key=key or None)
                from openjarvis.core.types import Message, Role

                result = engine.generate(
                    [Message(role=Role.USER, content="Responde únicamente: listo")],
                    model="openai/gpt-oss-120b",
                    max_tokens=256,
                )
                if not result["content"].strip():
                    return "Clave guardada, pero la prueba no devolvió texto. Vuelve a comprobar."
                return "Groq comprobado. Selecciona su perfil y pulsa Aplicar y reconectar."
            except Exception as exc:
                return credential_error(exc)
            finally:
                if engine:
                    engine.close()

        self.busy = True
        self.stop_listening()
        self.window.set_busy(True)
        self.window.credential_status.setText("Comprobando Groq…")
        job = Job(check, self)

        def done(message):
            self.busy = False
            self.window.set_busy(False)
            self.window.credential_status.setText(str(message))
            self.resume_listening()

        job.result.connect(done)
        job.error.connect(lambda _error: done("No se pudo comprobar la credencial."))
        self._track(job)

    def _forget(self, job):
        self.jobs.discard(job)
        job.deleteLater()

    @Slot(str)
    def set_state(self, state):
        if self.closing:
            return
        self.window.status.setText(STATES.get(state, state))
        key = state if state in STATES else "idle"
        if "Reconociendo" in state:
            key = "transcribing"
        elif any(text in state for text in ["Habla ahora", "Te escucho", "Escuchando"]):
            key = "listening"
        if self.brain:
            self.brain.status = key
        self.state_changed.emit(key)

    @Slot(str)
    def connect_brain(self, profile_name):
        if self.busy or self.voice_loading or self.closing:
            return
        try:
            settings = load_settings(profile_name=profile_name)
            settings.profile.validate_credentials()
        except Exception as exc:
            if self.brain is None:
                self._startup_failed(str(exc))
            else:
                self.fail(str(exc))
            return
        self.stop_listening()
        self.busy = True
        self.window.set_busy(True)
        self._pending_settings = settings
        # Let the microphone worker release its stream before closing backends.
        self._connect_timer = QTimer(self)
        self._connect_timer.timeout.connect(self._connect_when_stopped)
        self._connect_timer.start(50)

    @Slot()
    def _connect_when_stopped(self):
        if self.listener is not None and self.listener.isRunning():
            return
        self._connect_timer.stop()
        self._connect_timer.deleteLater()
        if self.closing:
            return
        previous_session = self.brain._history.active_id if self.brain else "principal"
        if self.brain:
            self.brain.close()
        self.settings = self._pending_settings
        self.brain = JarvisBrain(
            settings=self.settings,
            confirm_callback=self.bridge.confirm,
            appearance=self.appearance,
            desktop_access=self.desktop_access,
        )
        self.brain._history.activate(previous_session)
        job = StartupJob(self.brain, self)
        job.state.connect(self.set_state)
        job.result.connect(self._engine_ready)
        job.error.connect(self._startup_failed)
        self.set_state("boot")
        self._track(job)

    @Slot(object)
    def _engine_ready(self, _result):
        if self.closing:
            return
        self.busy = False
        self.companion.update_context()
        self.brain.camera_source = self.companion.capture_camera
        self.window.set_busy(False)
        self.window.model_status.setText(
            f"Conectado: {self.brain.profile.label}\nModelo: {self.brain.model}"
        )
        self.window.model_chip.setText(self.brain.model)
        from openjarvis.core.events import EventType

        for event_type in [EventType.TOOL_CALL_START, EventType.TOOL_CALL_END]:
            self.brain._jarvis._bus.subscribe(event_type, self.tool_event.emit)
        self.window.tool_list.clear()
        for tool in self.brain._agent._tools:
            item = QListWidgetItem(f"{tool.spec.name} · {tool.spec.category or 'general'}")
            item.setData(256, tool.spec.description)
            self.window.tool_list.addItem(item)
        self.refresh_sessions()
        if self.schedules is None:
            from scheduling import NativeSchedules

            def background_brain():
                return JarvisBrain(
                    settings=self.settings,
                    data_dir=DATA_DIR / "jobs",
                    appearance=self.appearance,
                    desktop_access=self.desktop_access,
                )

            self.schedules = NativeSchedules(
                DATA_DIR / "scheduler.sqlite3",
                background_brain,
                self.scheduled_result.emit,
            )
        self.refresh_schedules()
        if not self._loaded_history:
            rows = self.brain._history.recent()
            for role, content in rows:
                self.window.append_message(role, content)
            if not rows:
                self.window.append_message(
                    "assistant",
                    "Estoy aquí. Puedes escribirme o pulsar «Hablar ahora». El "
                    "estado de voz te mostrará cuándo estoy listo para escuchar.",
                )
            self._loaded_history = True
        try:
            import tomlkit

            document = tomlkit.parse(PROFILE_PATH.read_text(encoding="utf-8"))
            document["active"] = self.settings.profile.name
            temp = PROFILE_PATH.with_suffix(".toml.tmp")
            temp.write_text(tomlkit.dumps(document), encoding="utf-8")
            temp.replace(PROFILE_PATH)
        except OSError:
            log.exception("No se pudo guardar el perfil")
        self.voice_loading = True
        self.window.voice_status.setText(
            "Cargando reconocimiento y voz en español… El chat ya está disponible."
        )
        self.window.heard.setText(
            "Micrófono listo. Di «Jarvis» o pulsa «Hablar ahora»."
            if self.brain.voice_ready
            else "Preparando el micrófono y la voz… Ya puedes escribir."
        )
        self.set_state("idle")
        self.refresh_diagnostics()
        job = Job(self.brain._init_voice, self)
        job.result.connect(self._voice_ready)
        job.error.connect(self._voice_failed)
        self._track(job)

    @Slot(str)
    def _startup_failed(self, error):
        self.busy = False
        self.window.set_busy(True)
        self.window.retry.setEnabled(True)
        self.window.apply_model.setEnabled(True)
        self.fail(error)
        self.window.model_status.setText(
            "No se pudo iniciar el modelo. Pulsa «Aplicar y reconectar»."
        )
        if "necesita" in error and "KEY" in error:
            self.window.show_page(2)
            self.window.model_status.setText(
                "Bienvenido. Introduce tu propia clave de Groq y pulsa Guardar y comprobar. "
                "Después pulsa Aplicar y reconectar. "
                "Tus datos y tu clave pertenecen a esta cuenta de Windows."
            )

    @Slot(object)
    def _voice_ready(self, _result):
        self.voice_loading = False
        if self.closing:
            return
        self.window.heard.setText("Micrófono listo · di «Jarvis» o pulsa «Hablar ahora».")
        self.window.voice_status.setText(
            f"Reconocimiento: {'listo' if self.brain.voice_ready else 'no disponible'}\n"
            f"Voz en español: {'lista' if self.brain.speech_ready else 'no disponible'}"
        )
        self.refresh_diagnostics()
        if self.brain.speech_ready and not self._greeted and not self.busy:
            self._greeted = True
            self.speak("Ya estoy aquí. Vamos paso a paso; dime qué necesitas.")
        else:
            self.resume_listening()

    @Slot(str)
    def _voice_failed(self, error):
        self.voice_loading = False
        self.window.voice_status.setText(f"No pude preparar la voz: {error}")
        self.fail(error)

    def stop_listening(self):
        if self.listener:
            self.listener.stop()

    @Slot()
    def restart_listening(self):
        self.stop_listening()
        QTimer.singleShot(200, self.resume_listening)

    @Slot()
    def resume_listening(self):
        if self.closing or self.busy or self.voice_loading or self._speech_blocked:
            return
        if self.listener is not None and self.listener.isRunning():
            if self.listener.cancelled.is_set():
                QTimer.singleShot(150, self.resume_listening)
            return
        if (
            self.brain
            and self.brain.ready
            and self.brain.voice_ready
            and self.window.continuous.isChecked()
        ):
            self._start_listening(once=False)
        else:
            self.set_state("idle")

    def _start_listening(self, *, once):
        if not self.brain or not self.brain.voice_ready:
            self.set_state("La voz aún se está preparando. Puedes escribir mientras tanto.")
            return
        job = ListenJob(
            self.brain,
            device=self.window.microphone.currentData(),
            threshold=self.window.threshold.value(),
            once=once,
            require_wake=self.window.require_wake.isChecked(),
            followup_until=self._followup_until,
        )
        self.listener = job
        job.state.connect(self.set_state)
        job.level.connect(self.window.level.setValue)
        job.heard.connect(lambda text: self.window.heard.setText(f"Te escuché: {text}"))
        job.command.connect(self.submit)
        job.error.connect(self._listen_failed)
        job.finished.connect(self._listen_finished)
        self._track(job)

    @Slot()
    def _listen_finished(self):
        self.listener = None
        self.window.level.setValue(0)

    @Slot(str)
    def _listen_failed(self, error):
        self._speech_blocked = True
        self.window.voice_status.setText(error)
        self.fail(error)

    @Slot()
    def listen_once(self):
        if self.busy or self.closing:
            return
        self._speech_blocked = False
        self.stop_listening()
        self._listen_timer = QTimer(self)

        def begin():
            if self.listener is not None and self.listener.isRunning():
                return
            self._listen_timer.stop()
            self._listen_timer.deleteLater()
            self._start_listening(once=True)

        self._listen_timer.timeout.connect(begin)
        self._listen_timer.start(70)

    @Slot(str)
    def submit(self, text):
        if self.busy or self.closing or not self.brain or not self.brain.ready:
            return
        if self.companion.handle_command(text):
            self.window.input.clear()
            return
        self.stop_listening()
        self.busy = True
        self.window.set_busy(True)
        self.window.input.clear()
        self.window.append_message("user", text)
        self._request_started = time.perf_counter()
        self.window.latency.setText("Generando respuesta…")
        self.set_state("thinking")
        job = Job(lambda: self.brain.ask(text, on_text=self.partial_text.emit), self)
        job.result.connect(self._answer)
        job.error.connect(self._request_failed)
        self._track(job)

    @Slot(object)
    def _answer(self, answer):
        if self.closing:
            return
        self.window.append_message("assistant", str(answer))
        if self._request_started is not None:
            seconds = time.perf_counter() - self._request_started
            self.window.latency.setText(f"Última respuesta · {seconds:.1f} s")
        self.refresh_sessions()
        self.busy = False
        if self.brain.last_error:
            self.window.set_busy(False)
            self.set_state("idle")
            self.window.add_activity(self.brain.last_error)
            self.resume_listening()
        elif self.window.read_replies.isChecked() and self.brain.speech_ready:
            self.speak(str(answer))
        else:
            self.window.set_busy(False)
            self.resume_listening()

    @Slot(str)
    def _request_failed(self, error):
        self.busy = False
        self.window.set_busy(False)
        self.fail(error)

    @Slot()
    def test_voice(self):
        if self.busy or self.voice_loading:
            self.set_state("Espera a que termine la operación actual para probar la voz.")
            return
        self.speak("Hola, señor. Soy Jarvis. Esta es mi prueba de voz en español.")

    def speak(self, text):
        text = spoken_reply(text)
        if not text:
            return
        if not self.brain or not self.brain.speech_ready:
            self.fail("La voz todavía no está disponible. Pulsa Reconectar para prepararla.")
            return
        self.stop_listening()
        self.busy = True
        self.window.set_busy(True)
        self.set_state("speaking")
        device = self.window.speaker.currentData()
        # Keep spoken answers concise; the complete response remains visible.
        spoken = (
            text
            if len(text) <= 600
            else text[:600].rsplit(" ", 1)[0] + ". El resto está en la conversación."
        )
        job = Job(lambda: self.brain.speak(spoken, output_device=device), self)
        job.result.connect(self._spoken)
        job.error.connect(self._speak_failed)
        self._track(job)

    @Slot(object)
    def _spoken(self, _result):
        self.busy = False
        self.window.set_busy(False)
        cfg = self.companion.focus.settings
        self._followup_until = time.monotonic() + 15 if cfg.enabled and cfg.followup else 0
        self.refresh_diagnostics()
        self.resume_listening()

    @Slot(str)
    def _speak_failed(self, error):
        self.busy = False
        self.window.set_busy(False)
        self.window.voice_status.setText(f"No se pudo reproducir la voz: {error}")
        self.fail(f"Voz: {error}. Revisa la salida en «Voz y micrófono».")

    @Slot(str)
    def fail(self, error):
        if self.brain:
            self.brain.last_error = error
            self.brain.status = "error"
        self.window.status.setText(f"Necesita atención: {error}")
        self.state_changed.emit("error")
        self.refresh_diagnostics()

    def refresh_diagnostics(self):
        brain = self.brain
        tools = getattr(brain, "_available_tool_names", [])
        self.window.diagnostics.setPlainText(
            f"Cerebro: {'conectado' if brain and brain.ready else 'sin conexión'}\n"
            f"Perfil: {brain.profile.label if brain else 'preparando'}\n"
            "Reconocimiento de voz: "
            f"{'listo' if brain and brain.voice_ready else 'no disponible'}\n"
            f"Salida hablada: {'lista' if brain and brain.speech_ready else 'no disponible'}\n"
            f"Último aviso: {(brain.last_error if brain else '') or 'ninguno'}\n\n"
            f"Herramientas cargadas ({len(tools)}):\n" + "\n".join(f"• {tool}" for tool in tools)
        )

    @Slot()
    def shutdown(self):
        if self.closing:
            return
        self.closing = True
        self.window.hide()
        self.closing_started.emit()
        self.desktop_access.stopped.set()
        if self.schedules:
            self.schedules.adapter.stopping.set()
        if self.brain:
            self.brain.cancel()
        self.companion.close()
        self.window.status.setText("Cerrando Jarvis al terminar la operación actual…")
        self.window.set_busy(True)
        self.stop_listening()
        self.bridge.cancel_pending()
        self.shutdown_timer.start(100)

    @Slot()
    def _finish_shutdown(self):
        if any(job.isRunning() for job in self.jobs):
            return
        if self.companion.presence_worker and self.companion.presence_worker.isRunning():
            return
        if self.schedules and self.schedules.adapter.active.is_set():
            return
        self.shutdown_timer.stop()
        if self.brain:
            self.brain.close()
        if self.schedules:
            self.schedules.close()
        self.window.preferences.sync()
        self.stopped.emit()

    @Slot(object)
    def _tool_event(self, event):
        from openjarvis.core.events import EventType

        name = event.data.get("tool", "herramienta")
        if event.event_type == EventType.TOOL_CALL_START:
            self.set_state("tool")
            self.window.status.setText(f"Ejecutando · {name}")
            self.window.stream_text("")
            self.window.add_activity(f"En ejecución · {name}")
        else:
            success = event.data.get("success", True)
            self.window.add_activity(f"{'Completado' if success else 'Falló'} · {name}")
            self.set_state("thinking")

    def refresh_sessions(self):
        if not self.brain:
            return
        self.window.sessions.blockSignals(True)
        self.window.sessions.clear()
        for row in self.brain._history.conversations():
            item = QListWidgetItem(row["title"])
            item.setData(256, row["id"])
            self.window.sessions.addItem(item)
            if row["id"] == self.brain._history.active_id:
                self.window.sessions.setCurrentItem(item)
        self.window.sessions.blockSignals(False)

    @Slot()
    def new_conversation(self):
        if self.busy or not self.brain or not self.brain.ready:
            return
        self.brain._history.create()
        self.window.reset_messages([])
        self.window.show_page(0)
        self.refresh_sessions()

    @Slot(str)
    def select_conversation(self, identifier):
        if self.busy or not self.brain:
            return
        self.brain._history.activate(identifier)
        self.window.reset_messages(self.brain._history.recent())

    @Slot(bool)
    def set_desktop_enabled(self, enabled):
        self.desktop_access.enabled = enabled
        if enabled:
            self.desktop_access.stopped.clear()
        self.window.add_activity(
            "Control de pantalla activado" if enabled else "Control de pantalla en pausa"
        )

    @Slot()
    def stop_current(self):
        self._followup_until = 0
        self.companion.focus.snooze()
        self.companion.deferred = None
        self.companion.manual_pending = ""
        if self.companion.focus.phase in {"focus", "break"} and not self.companion.focus.paused:
            self.companion.focus.toggle_pause()
        self.companion.refresh()
        self.desktop_access.stopped.set()
        self.window.panels.allow_control.setChecked(False)
        self.stop_listening()
        if self.brain:
            self.brain.cancel()
        import sounddevice

        sounddevice.stop()
        self.window.add_activity("Interrupción solicitada por el usuario")
        self.set_state("paused")

    @Slot(str)
    def test_desktop(self, action):
        if self.busy or not self.brain or not self.brain.ready:
            return
        import json

        from openjarvis.core.types import ToolCall

        editor = self.window.panels.test_editor
        self.window.show_page(4)
        if action == "move":
            point = editor.mapToGlobal(editor.rect().center())
            ratio = editor.screen().devicePixelRatio()
            params = {
                "action": action,
                "x": round(point.x() * ratio),
                "y": round(point.y() * ratio),
            }
        else:
            editor.setFocus()
            params = {
                "action": "type_text",
                "text": "Jarvis controla el teclado: español, acción y precisión.",
            }
        self.stop_listening()
        self.busy = True
        self.window.set_busy(True)
        self.brain.cancelled.clear()
        job = Job(
            lambda: self.brain._agent._executor.execute(
                ToolCall(
                    id="desktop-demo",
                    name="desktop_control",
                    arguments=json.dumps(params),
                )
            ),
            self,
        )
        job.result.connect(self._desktop_test_done)
        job.error.connect(self._request_failed)
        self._track(job)

    @Slot(object)
    def _desktop_test_done(self, result):
        if result.success:
            data = json.loads(result.content)
            if "typed_characters" in data:
                message = f"Texto escrito correctamente ({data['typed_characters']} caracteres)."
            else:
                message = "Movimiento del ratón completado en la zona de prueba."
        else:
            message = f"No se pudo completar la prueba: {result.content}"
        self.window.panels.desktop_result.setText(message)
        self.busy = False
        self.window.set_busy(False)
        self.resume_listening()

    @Slot(str)
    def save_memory(self, text):
        if not text or self.busy or not self.brain or not self.brain.ready:
            return

        def save():
            self.brain._jarvis.memory._get_backend().store(text, source="nota del usuario")
            return "Nota guardada. Puedes buscarla por sus palabras."

        self._memory_job(save)
        self.window.panels.note.clear()

    @Slot(str)
    def search_memory(self, query):
        if not query or self.busy or not self.brain or not self.brain.ready:
            return

        def search():
            rows = self.brain._jarvis.memory.search(query)
            return (
                "\n\n".join(f"{r['source']}\n{r['content']}" for r in rows)
                or "No encontré coincidencias."
            )

        self._memory_job(search)

    def _memory_job(self, operation):
        self.busy = True
        self.window.set_busy(True)
        job = Job(operation, self)
        job.result.connect(self._memory_done)
        job.error.connect(self._request_failed)
        self._track(job)

    @Slot(object)
    def _memory_done(self, result):
        self.window.panels.memory_results.setPlainText(str(result))
        self.busy = False
        self.window.set_busy(False)

    @Slot(str, int)
    def create_schedule(self, prompt, seconds):
        if not self.schedules:
            return
        try:
            self.schedules.create(prompt, seconds)
            self.window.panels.task_prompt.clear()
            self.refresh_schedules()
        except Exception as exc:
            self.fail(str(exc))

    @Slot(str)
    def toggle_schedule(self, identifier):
        if self.schedules and identifier:
            self.schedules.toggle(identifier)
            self.refresh_schedules()

    @Slot()
    def refresh_schedules(self):
        if not self.schedules:
            return
        panel = self.window.panels
        panel.tasks.clear()
        for task, logs in self.schedules.list():
            status = "Activa" if task.status == "active" else "Pausada"
            item = QListWidgetItem(f"{status} · {task.prompt[:80]}")
            item.setData(256, task.id)
            panel.tasks.addItem(item)
            panel.task_logs[task.id] = (
                "\n\n".join(
                    f"{row['started_at']} · {'Correcto' if row['success'] else 'Error'}\n"
                    f"{row['result'] or row['error']}"
                    for row in logs
                )
                or "Sin ejecuciones todavía."
            )

    @Slot(object)
    def on_scheduled_result(self, data):
        self.window.add_activity(
            "Tarea programada completada" if data.get("success") else "Falló una tarea programada"
        )
        self.refresh_schedules()
