"""Functional workspace pages: desktop, memory, schedules and appearance."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from appearance import PALETTE, STATE_LABELS


class WorkspacePanels(QObject):
    memory_search = Signal(str)
    memory_save = Signal(str)
    schedule_create = Signal(str, int)
    schedule_toggle = Signal(str)
    schedule_refresh = Signal()
    desktop_test = Signal(str)
    desktop_enabled = Signal(bool)
    palette_set = Signal(str, str)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.colors = dict(PALETTE)
        self.color_buttons = {}
        self._desktop()
        self._memory()
        self._schedules()
        self._appearance()

    def page(self, title, subtitle):
        page, layout = QWidget(), QVBoxLayout()
        page.setLayout(layout)
        layout.setContentsMargins(0, 5, 0, 0)
        caption = QLabel(subtitle)
        caption.setObjectName("muted")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        index = self.window.stack.addWidget(page)
        button = QPushButton(title)
        button.setCheckable(True)
        button.clicked.connect(lambda: self.window.show_page(index))
        self.window.nav_layout.addWidget(button)
        self.window.nav.append(button)
        return layout

    def _desktop(self):
        box = self.page("Control de pantalla", "Ratón, teclado y observación del escritorio.")
        self.allow_control = QCheckBox("Permitir que Jarvis controle el escritorio")
        self.allow_control.setChecked(True)
        self.allow_control.toggled.connect(self.desktop_enabled.emit)
        box.addWidget(self.allow_control)
        box.addWidget(QLabel("Zona de prueba · las demostraciones actúan dentro de este cuadro"))
        self.test_editor = QPlainTextEdit()
        self.test_editor.setAccessibleName("Zona de prueba de teclado")
        self.test_editor.setPlaceholderText("Aquí aparecerá el texto escrito por Jarvis.")
        box.addWidget(self.test_editor, 1)
        row = QHBoxLayout()
        for text, action in [
            ("Probar movimiento del ratón", "move"),
            ("Probar escritura en español", "type_text"),
        ]:
            button = QPushButton(text)
            button.clicked.connect(
                lambda _checked=False, action=action: self.desktop_test.emit(action)
            )
            row.addWidget(button)
        box.addLayout(row)
        self.desktop_result = QLabel("Listo para una prueba local.")
        self.desktop_result.setWordWrap(True)
        box.addWidget(self.desktop_result)
        caption = QLabel(
            "Puedes detener una tarea con «Detener». Mover el ratón a una esquina "
            "de la pantalla interrumpe los controles de PyAutoGUI."
        )
        caption.setWordWrap(True)
        caption.setObjectName("muted")
        box.addWidget(caption)

    def _memory(self):
        box = self.page("Memoria", "Guarda notas y recupera información de tu memoria documental.")
        search = QHBoxLayout()
        self.memory_query = QLineEdit()
        self.memory_query.setPlaceholderText("Buscar en los recuerdos de Jarvis…")
        button = QPushButton("Buscar")
        button.clicked.connect(lambda: self.memory_search.emit(self.memory_query.text().strip()))
        self.memory_query.returnPressed.connect(button.click)
        search.addWidget(self.memory_query, 1)
        search.addWidget(button)
        box.addLayout(search)
        self.memory_results = QPlainTextEdit()
        self.memory_results.setReadOnly(True)
        self.memory_results.setPlaceholderText("Los resultados de tu búsqueda aparecerán aquí.")
        box.addWidget(self.memory_results, 1)
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(90)
        self.note.setPlaceholderText("Escribe una nota que quieras que Jarvis recuerde.")
        box.addWidget(self.note)
        save = QPushButton("Guardar nota en la memoria")
        save.clicked.connect(lambda: self.memory_save.emit(self.note.toPlainText().strip()))
        box.addWidget(save)

    def _schedules(self):
        box = self.page(
            "Tareas programadas", "Trabajos recurrentes mientras Jarvis permanece abierto."
        )
        self.task_prompt = QPlainTextEdit()
        self.task_prompt.setMaximumHeight(90)
        self.task_prompt.setPlaceholderText("¿Qué debe hacer Jarvis? Describe una tarea concreta.")
        box.addWidget(self.task_prompt)
        row = QHBoxLayout()
        self.frequency = QComboBox()
        for label, seconds in [
            ("Cada 5 minutos", 300),
            ("Cada 15 minutos", 900),
            ("Cada hora", 3600),
            ("Cada día", 86400),
        ]:
            self.frequency.addItem(label, seconds)
        create = QPushButton("Programar tarea")
        create.setObjectName("primary")
        create.clicked.connect(
            lambda: self.schedule_create.emit(
                self.task_prompt.toPlainText().strip(),
                self.frequency.currentData(),
            )
        )
        row.addWidget(self.frequency)
        row.addWidget(create)
        box.addLayout(row)
        self.tasks = QListWidget()
        self.tasks.currentItemChanged.connect(self._selected_task)
        box.addWidget(self.tasks, 1)
        self.task_log = QPlainTextEdit()
        self.task_log.setReadOnly(True)
        self.task_log.setMaximumHeight(120)
        self.task_log.setPlaceholderText(
            "Selecciona una tarea para consultar sus últimas ejecuciones."
        )
        box.addWidget(self.task_log)
        row = QHBoxLayout()
        refresh = QPushButton("Actualizar")
        refresh.clicked.connect(self.schedule_refresh.emit)
        toggle = QPushButton("Pausar / reanudar seleccionada")
        toggle.clicked.connect(
            lambda: self.schedule_toggle.emit(
                self.tasks.currentItem().data(256) if self.tasks.currentItem() else "",
            )
        )
        row.addWidget(refresh)
        row.addWidget(toggle)
        box.addLayout(row)
        self.task_logs = {}

    def _selected_task(self, item, _previous):
        if item is not None:
            self.task_log.setPlainText(
                self.task_logs.get(item.data(256), "Sin ejecuciones todavía.")
            )

    def _appearance(self):
        box = self.page("Holograma", "Un color para cada acción. Los cambios quedan guardados.")
        form = QFormLayout()
        for state, text in STATE_LABELS.items():
            button = QPushButton(PALETTE[state])
            button.clicked.connect(lambda _checked=False, state=state: self.choose_color(state))
            self.color_buttons[state] = button
            form.addRow(text, button)
        box.addLayout(form)
        example = QLabel(
            "También puedes pedir: «Cambia el holograma a rojo» o «Ponlo verde cuando escuches»."
        )
        example.setWordWrap(True)
        example.setObjectName("muted")
        box.addWidget(example)
        box.addStretch()
        self.update_palette(self.colors)

    def choose_color(self, state):
        from PySide6.QtGui import QColor

        color = QColorDialog.getColor(
            QColor(self.colors[state]), self.window, "Color del holograma"
        )
        if color.isValid():
            self.palette_set.emit(state, color.name())

    def update_palette(self, colors):
        self.colors = colors
        for state, button in self.color_buttons.items():
            color = colors[state]
            button.setText(color)
            button.setStyleSheet(f"background:{color};color:#0b101a;font-weight:600")
