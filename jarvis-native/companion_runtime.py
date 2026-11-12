"""Qt integration: bounded proactive messages, serialized speech and optional presence."""

from __future__ import annotations

import time
from dataclasses import replace

from PySide6.QtCore import QObject, QTimer, Signal

from attention import PresenceWorker, foreground_observation
from companion import CompanionStore, Cue, FocusCompanion, Observation, companion_command


class CompanionRuntime(QObject):
    avatar_changed = Signal(bool)
    gaze_changed = Signal(object)
    notification = Signal(str)

    def __init__(self, desktop, directory):
        super().__init__(desktop)
        self.desktop, self.panel = desktop, desktop.window.companion_panel
        self.focus = FocusCompanion(CompanionStore(directory / "companion.sqlite3"))
        self.panel.apply_settings(self.focus.settings)
        self.panel.start.connect(self.start)
        self.panel.pause.connect(self.pause)
        self.panel.finish.connect(self.finish)
        self.panel.support.connect(self.support)
        self.panel.snooze.connect(self.snooze)
        self.panel.save.connect(self.save)
        self.panel.camera.connect(self.camera)
        self.panel.avatar.connect(self.set_avatar)
        # Privacy controls take effect immediately, without waiting for Save.
        self.panel.enabled.toggled.connect(lambda _on: self.save(self.panel.settings()))
        self.panel.observe.toggled.connect(lambda _on: self.save(self.panel.settings()))
        self.panel.spoken.toggled.connect(lambda _on: self.save(self.panel.settings()))
        self.panel.followup.toggled.connect(lambda _on: self.save(self.panel.settings()))
        desktop.state_changed.connect(self.panel.face.set_state)
        self.presence_worker = None
        self.presence, self.presence_at = None, 0
        self.last_message = ""
        self.manual_pending = ""
        self.deferred = None
        self._camera_announcement = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(5000)
        self.refresh()

    def idle(self):
        desk = self.desktop
        return bool(
            not desk.closing
            and not desk.busy
            and not desk.voice_loading
            and desk.brain
            and desk.brain.ready
        )

    def update_context(self):
        if self.desktop.brain:
            context = self.focus.context()
            if context and self.last_message:
                context += f"Tu último mensaje como compañero fue: {self.last_message[:400]}"
            self.desktop.brain.companion_context = context

    def refresh(self):
        self.panel.refresh(
            self.focus.snapshot(), self.focus.store.summary(), self.focus.store.recent()
        )
        self.update_context()

    def tick(self):
        if self.desktop.closing:
            return
        now = time.monotonic()
        cfg = self.focus.settings
        # Foreground titles are read only for an active, unpaused focus session.
        if (
            cfg.enabled
            and cfg.observe_apps
            and self.focus.phase == "focus"
            and not self.focus.paused
        ):
            observation = foreground_observation()
            classification = (
                self.focus.classify(observation) if observation.available else "unknown"
            )
            self.panel.sensor_status.setText(
                "Posible ocio detectado; esperando una permanencia sostenida."
                if classification == "distraction"
                else "Reglas locales activas. Sin coincidencia de ocio."
            )
        else:
            # Just last-input idle time, without keeping an app/title, for check-ins.
            observation = Observation(idle_seconds=self.input_idle())
            self.panel.sensor_status.setText("Detección de aplicaciones en pausa.")
        if self.presence is not None and now - self.presence_at < 10:
            observation = replace(observation, present=self.presence)
        cue = self.focus.tick(observation, now=now, can_interrupt=self.idle())
        if cue:
            self.deliver(cue)
        elif self.manual_pending and self.idle():
            text, self.manual_pending = self.manual_pending, ""
            self.support(text)
        elif self.deferred and self.idle():
            cue, self.deferred = self.deferred, None
            self.deliver(cue)
        self.refresh()

    @staticmethod
    def input_idle():
        # Avoid reading foreground content outside a session.
        import ctypes
        from ctypes import wintypes

        class Last(ctypes.Structure):
            _fields_ = [("size", wintypes.UINT), ("tick", wintypes.DWORD)]

        try:
            last = Last(ctypes.sizeof(Last), 0)
            user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
            kernel.GetTickCount64.restype = ctypes.c_ulonglong
            if user.GetLastInputInfo(ctypes.byref(last)):
                return ((kernel.GetTickCount64() - last.tick) & 0xFFFFFFFF) / 1000
        except (AttributeError, OSError):
            pass
        return 0

    def deliver(self, cue, *, speak=True):
        self.focus.store.event(cue, self.focus.session_id)
        self.last_message = cue.text
        self.panel.advice.setText(cue.text)
        desk = self.desktop
        desk.window.add_activity(f"Compañero · {cue.text}")
        if desk.brain and desk.brain.ready:
            desk.window.append_message("assistant", cue.text)
        self.notification.emit(cue.text)
        self.refresh()
        if speak and self.focus.settings.spoken and self.idle() and desk.brain.speech_ready:
            desk.speak(cue.text)

    def announce(self, cue):
        # Session controls remain usable during a long chat request, but never
        # steal its microphone, speech or partial answer.
        if not self.idle():
            self.deferred = cue
            self.panel.advice.setText(cue.text)
            self.refresh()
        else:
            self.deliver(cue)

    def start(self, goal, minutes):
        try:
            self.save(self.panel.settings(), announce=False)
            self.announce(self.focus.start(goal, minutes))
        except ValueError as exc:
            self.panel.advice.setText(str(exc))

    def pause(self):
        self.announce(self.focus.toggle_pause())

    def finish(self):
        self.deferred = None
        self.announce(self.focus.finish())

    def snooze(self):
        self.focus.snooze()
        self.deferred, self.manual_pending = None, ""
        self.deliver(
            Cue("silence", "De acuerdo. No iniciaré avisos durante diez minutos."), speak=False
        )

    def save(self, settings, *, announce=True):
        try:
            self.focus.configure(settings)
            self.avatar_changed.emit(settings.avatar)
            if not settings.enabled:
                self.deferred = None
            if not settings.enabled or not settings.followup:
                self.desktop._followup_until = 0
            if announce:
                self.panel.advice.setText("Tu acompañamiento quedó guardado.")
            self.refresh()
        except (ValueError, OSError) as exc:
            self.panel.advice.setText(f"No se pudo guardar: {exc}")

    def set_avatar(self, enabled):
        self.save(replace(self.focus.settings, avatar=enabled), announce=False)

    def support(self, text="Me distraje. Ayúdame a volver al foco con un paso pequeño."):
        if not self.idle():
            self.manual_pending = text
            self.panel.advice.setText("Te ayudo en cuanto termine la respuesta actual.")
            return
        from desktop import Job

        desk = self.desktop
        desk.stop_listening()
        desk.busy = True
        desk.window.set_busy(True)
        desk.window.append_message("user", text)
        desk.brain.cancelled.clear()
        desk.set_state("thinking")
        self.update_context()
        brain = desk.brain
        self._support_text = text
        job = Job(lambda: brain.companion_reply(text, self.focus.settings.style), desk)
        job.result.connect(self._support_result)
        job.error.connect(self._support_error)
        desk._track(job)

    def _support_result(self, answer):
        self._support_done(self._support_text, str(answer))

    def _support_error(self, _error):
        self.panel.advice.setText("No se pudo consultar al modelo; seguimos con apoyo local.")
        self._support_done(
            self._support_text,
            "No pasa nada por distraerte. Elige una sola acción "
            "que puedas terminar en dos minutos y empezamos por ahí.",
        )

    def _support_done(self, text, answer):
        desk = self.desktop
        if desk.closing:
            return
        desk.busy = False
        desk.window.set_busy(False)
        if desk.brain.cancelled.is_set():
            desk.resume_listening()
            return
        desk.brain._remember_turn(text, answer)
        self.deliver(Cue("support", answer))
        if not desk.busy:
            desk.resume_listening()

    def handle_command(self, text):
        command = companion_command(text)
        if command is None:
            return False
        action, args = command
        if action == "camera_status":
            self.desktop.window.append_message("user", text)
            if not self.panel.camera_enabled.isChecked():
                message = "La cámara está apagada. Puedes pedirme que la encienda."
            elif self.presence_at and time.monotonic() - self.presence_at < 10:
                message = (
                    "La cámara está activa y el detector encuentra un rostro. "
                    "Solo compruebo presencia; no estoy interpretando lo que haces."
                    if self.presence
                    else "La cámara está activa, pero ahora no detecta un rostro."
                )
            else:
                message = "La cámara se está preparando. Te avisaré si no puede abrirse."
            self.deliver(Cue("camera", message))
            return True
        if action in {"camera_on", "camera_off"}:
            self.desktop.window.append_message("user", text)
            self._camera_announcement = action == "camera_on"
            already_on = self.panel.camera_enabled.isChecked()
            self.panel.camera_enabled.setChecked(action == "camera_on")
            self.panel.advice.setText(
                "Abriendo la cámara local…" if action == "camera_on" else "Cámara apagada."
            )
            if action == "camera_off":
                self.deliver(Cue("camera", "Apagando la cámara."), speak=False)
            elif already_on:
                self._camera_announcement = False
                self.deliver(Cue("camera", "La cámara ya está activada."), speak=False)
            return True
        if action == "support":
            self.support(text)
            return True
        self.desktop.window.append_message("user", text)
        if action == "start":
            self.panel.goal.setText(args["goal"])
            if args["minutes"] is not None:
                if not 1 <= args["minutes"] <= 120:
                    self.announce(Cue("info", "Elige entre 1 y 120 minutos de enfoque."))
                    return True
                self.panel.minutes.setValue(args["minutes"])
            self.start(args["goal"], self.panel.minutes.value())
        elif action in {"pause", "resume"}:
            desired = action == "pause"
            if self.focus.phase in {"focus", "break"} and self.focus.paused == desired:
                self.announce(
                    Cue(
                        "info",
                        "La sesión ya está en pausa." if desired else "La sesión sigue en curso.",
                    )
                )
            else:
                self.pause()
        elif action == "finish":
            self.finish()
        else:
            self.snooze()
        return True

    def camera(self, enabled):
        self.panel.camera_index.setEnabled(not enabled)
        self.panel.camera_backend.setEnabled(not enabled)
        if not enabled:
            if self.presence_worker:
                self.presence_worker.stop()
            self.presence = None
            self.panel.face.point = None
            self.gaze_changed.emit(None)
            self.panel.camera_status.setText("Cámara apagada. La cara sigue el cursor.")
            return
        if self.presence_worker is not None:
            return
        self.panel.camera_status.setText("Abriendo cámara local…")
        worker = PresenceWorker(
            self.desktop,
            index=self.panel.camera_index.value(),
            backend=self.panel.camera_backend.currentData(),
        )
        self.presence_worker = worker
        worker.sample.connect(self._presence)
        worker.error.connect(self._camera_error)
        worker.opened.connect(self._camera_opened)
        worker.finished.connect(self._camera_stopped)
        self.desktop._track(worker)

    def _camera_opened(self, message):
        if not self.panel.camera_enabled.isChecked():
            return
        self.panel.camera_status.setText(message)
        if self._camera_announcement:
            self._camera_announcement = False
            self.deliver(Cue("camera", "Ya encendí la cámara. La imagen se procesa en tu equipo."))

    def capture_camera(self):
        if self.presence_worker is None:
            raise RuntimeError("Primero activa la cámara en Compañero o di «enciende la cámara».")
        return self.presence_worker.snapshot()

    def _presence(self, sample):
        if not self.panel.camera_enabled.isChecked() or self.desktop.closing:
            return
        self.presence, self.presence_at = sample["present"], time.monotonic()
        self.panel.face.point = sample["point"]
        self.gaze_changed.emit(sample["point"])
        self.panel.camera_status.setText(
            "Cámara local activa · rostro detectado."
            if self.presence
            else "Cámara local activa · sin rostro detectado."
        )

    def _camera_error(self, message):
        self.panel.camera_enabled.setChecked(False)
        self.panel.camera_status.setText(message)
        if self._camera_announcement:
            self._camera_announcement = False
            self.deliver(Cue("camera", message), speak=False)

    def _camera_stopped(self):
        self.presence_worker = None
        if not self.desktop.closing and self.panel.camera_enabled.isChecked():
            self.camera(True)

    def close(self):
        self.timer.stop()
        if self.presence_worker:
            self.presence_worker.stop()
        if self.focus.session_id is not None:
            self.focus.finish("interrumpida")
