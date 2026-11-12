"""Spanish controls for companionship, focus and explicit local camera activation."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from avatar import CompanionFace
from companion import CompanionSettings


def spin(lower, upper, value):
    box = QSpinBox()
    box.setRange(lower, upper)
    box.setValue(value)
    return box


class CompanionPanel(QObject):
    start = Signal(str, int)
    pause = Signal()
    finish = Signal()
    support = Signal()
    snooze = Signal()
    save = Signal(object)
    camera = Signal(bool)
    avatar = Signal(bool)

    def __init__(self, window, page_factory):
        super().__init__(window)
        outer = page_factory(
            "Compañero", "Una presencia cercana para conversar, enfocarte y descansar."
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(0, 0, 12, 0)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.face = CompanionFace()
        box.addWidget(self.face)
        self.status = QLabel("A tu ritmo · elige una meta pequeña para empezar.")
        self.status.setObjectName("title")
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        self.progress = QLabel("Hoy: 0 bloques completados · 0 minutos de enfoque")
        self.progress.setObjectName("muted")
        box.addWidget(self.progress)
        self.goal = QLineEdit()
        self.goal.setPlaceholderText(
            "¿En qué quieres avanzar? Por ejemplo: terminar una función de mi proyecto"
        )
        self.goal.setMaxLength(500)
        self.goal.setAccessibleName("Meta de enfoque")
        box.addWidget(self.goal)
        row = QHBoxLayout()
        self.minutes = spin(1, 120, 25)
        self.minutes.setSuffix(" min de enfoque")
        self.break_minutes = spin(1, 30, 5)
        self.break_minutes.setSuffix(" min de pausa")
        self.begin = QPushButton("Empezar conmigo")
        self.begin.setObjectName("primary")
        self.begin.clicked.connect(lambda: self.start.emit(self.goal.text(), self.minutes.value()))
        row.addWidget(self.minutes)
        row.addWidget(self.break_minutes)
        row.addWidget(self.begin)
        box.addLayout(row)
        row = QHBoxLayout()
        self.pause_button = QPushButton("Pausar sesión")
        self.pause_button.clicked.connect(self.pause.emit)
        finish = QPushButton("Terminar sesión")
        finish.clicked.connect(self.finish.emit)
        for button in [self.pause_button, finish]:
            row.addWidget(button)
        help_button = QPushButton("Me distraje · ayúdame")
        help_button.clicked.connect(self.support.emit)
        row.addWidget(help_button)
        mute = QPushButton("Silencio 10 min")
        mute.clicked.connect(self.snooze.emit)
        row.addWidget(mute)
        box.addLayout(row)
        self.advice = QLabel("Sin regaños: trabajamos con pasos pequeños y pausas reales.")
        self.advice.setWordWrap(True)
        box.addWidget(self.advice)
        self.enabled = QCheckBox(
            "Acompañamiento proactivo: permite que Jarvis inicie pequeños recordatorios"
        )
        self.spoken = QCheckBox("Hablar también los mensajes del compañero")
        self.followup = QCheckBox("Tras hablar, escuchar mi respuesta 15 s sin repetir «Jarvis»")
        self.observe = QCheckBox(
            "Detectar posibles distracciones por la aplicación y el título activos"
        )
        self.avatar_enabled = QCheckBox("Mostrar la cara del compañero en la burbuja flotante")
        self.avatar_enabled.toggled.connect(self.avatar.emit)
        for widget in [self.enabled, self.spoken, self.followup, self.observe, self.avatar_enabled]:
            box.addWidget(widget)
        self.camera_enabled = QCheckBox("Activar cámara local para presencia y mirada del avatar")
        self.camera_enabled.toggled.connect(self.camera.emit)
        box.addWidget(self.camera_enabled)
        camera_row = QHBoxLayout()
        self.camera_index = spin(0, 5, 0)
        self.camera_index.setPrefix("Cámara ")
        self.camera_index.setValue(window.preferences.value("camera_index", 0, type=int))
        self.camera_backend = QComboBox()
        for title, name in [
            ("Automático", "auto"),
            ("DirectShow", "dshow"),
            ("Media Foundation", "msmf"),
            ("Predeterminado", "default"),
        ]:
            self.camera_backend.addItem(title, name)
        self.camera_backend.setCurrentIndex(
            max(0, self.camera_backend.findData(window.preferences.value("camera_backend", "auto")))
        )
        self.camera_index.valueChanged.connect(
            lambda value: window.preferences.setValue("camera_index", value)
        )
        self.camera_backend.currentIndexChanged.connect(
            lambda _index: window.preferences.setValue(
                "camera_backend", self.camera_backend.currentData()
            )
        )
        camera_row.addWidget(self.camera_index)
        camera_row.addWidget(self.camera_backend)
        box.addLayout(camera_row)
        self.camera_status = QLabel(
            "Cámara apagada. La cara sigue el cursor; el compañero funciona sin cámara."
        )
        self.camera_status.setObjectName("muted")
        self.camera_status.setWordWrap(True)
        box.addWidget(self.camera_status)
        privacy = QLabel(
            "La cámara no se graba ni se envía a una IA. Detecta un rostro; no mide tu atención "
            "ni sabe cómo te sientes. Las reglas de ocio se evalúan localmente durante el enfoque."
        )
        privacy.setObjectName("muted")
        privacy.setWordWrap(True)
        box.addWidget(privacy)
        form = QFormLayout()
        self.style = QComboBox()
        for label, value in [
            ("Cercano y práctico", "cercano"),
            ("Suave y paciente", "suave"),
            ("Directo, sin regaños", "directo"),
        ]:
            self.style.addItem(label, value)
        form.addRow("Cómo te acompaño", self.style)
        self.checkin = spin(5, 180, 30)
        self.checkin.setSuffix(" min")
        form.addRow("Invitar a conversar cada", self.checkin)
        self.threshold = spin(15, 600, 45)
        self.threshold.setSuffix(" s continuos en ocio")
        form.addRow("Antes de un recordatorio", self.threshold)
        self.cooldown = spin(1, 30, 3)
        self.cooldown.setSuffix(" min entre recordatorios")
        form.addRow("Espacio entre avisos", self.cooldown)
        self.distractions = QLineEdit()
        self.allowed = QLineEdit()
        self.allowed.setPlaceholderText("Ejemplo: tutorial python, documentación; separa con comas")
        form.addRow("Contenido de ocio", self.distractions)
        form.addRow("Excepciones de trabajo", self.allowed)
        quiet = QHBoxLayout()
        self.quiet_start, self.quiet_end = spin(0, 23, 22), spin(0, 23, 8)
        quiet.addWidget(self.quiet_start)
        quiet.addWidget(QLabel("hasta"))
        quiet.addWidget(self.quiet_end)
        quiet.addStretch()
        form.addRow("Horas de silencio (0–23)", quiet)
        box.addLayout(form)
        save = QPushButton("Guardar mi acompañamiento")
        save.clicked.connect(lambda: self.save.emit(self.settings()))
        box.addWidget(save)
        self.sensor_status = QLabel("Detección local en espera de una sesión.")
        self.sensor_status.setWordWrap(True)
        self.sensor_status.setObjectName("muted")
        box.addWidget(self.sensor_status)
        box.addWidget(QLabel("Tus últimos momentos"))
        self.journal = QPlainTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setMaximumHeight(155)
        self.journal.setPlaceholderText("Aquí verás los avisos y los bloques que completes.")
        box.addWidget(self.journal)
        self.apply_settings(CompanionSettings())

    def apply_settings(self, settings):
        for widget, value in [
            (self.enabled, settings.enabled),
            (self.spoken, settings.spoken),
            (self.followup, settings.followup),
            (self.observe, settings.observe_apps),
            (self.avatar_enabled, settings.avatar),
        ]:
            widget.setChecked(value)
        self.minutes.setValue(settings.work_minutes)
        self.break_minutes.setValue(settings.break_minutes)
        self.style.setCurrentIndex(self.style.findData(settings.style))
        self.checkin.setValue(settings.checkin_minutes)
        self.threshold.setValue(settings.distraction_seconds)
        self.cooldown.setValue(settings.cooldown_seconds // 60)
        self.quiet_start.setValue(settings.quiet_start)
        self.quiet_end.setValue(settings.quiet_end)
        self.distractions.setText(settings.distractions)
        self.allowed.setText(settings.allowed)

    def settings(self):
        return CompanionSettings(
            enabled=self.enabled.isChecked(),
            spoken=self.spoken.isChecked(),
            avatar=self.avatar_enabled.isChecked(),
            observe_apps=self.observe.isChecked(),
            followup=self.followup.isChecked(),
            style=self.style.currentData(),
            work_minutes=self.minutes.value(),
            break_minutes=self.break_minutes.value(),
            checkin_minutes=self.checkin.value(),
            distraction_seconds=self.threshold.value(),
            cooldown_seconds=self.cooldown.value() * 60,
            quiet_start=self.quiet_start.value(),
            quiet_end=self.quiet_end.value(),
            distractions=self.distractions.text(),
            allowed=self.allowed.text(),
        )

    def refresh(self, snapshot, summary, events):
        phase = snapshot["phase"]
        if phase in {"focus", "break"}:
            minutes, seconds = divmod(snapshot["remaining"], 60)
            title = "Enfoque" if phase == "focus" else "Descanso"
            self.status.setText(
                f"{title} · {minutes:02}:{seconds:02}"
                + (" · En pausa" if snapshot["paused"] else "")
            )
        else:
            self.status.setText("Aquí contigo · ¿cuál es tu siguiente paso?")
        self.pause_button.setText("Reanudar sesión" if snapshot["paused"] else "Pausar sesión")
        self.begin.setEnabled(phase != "focus")
        self.progress.setText(
            f"Hoy: {summary['sessions']} bloques completados · "
            f"{summary['minutes']} minutos de enfoque"
        )
        self.journal.setPlainText(
            "\n\n".join(f"{stamp[11:16]} · {text}" for stamp, _kind, text in events)
        )
