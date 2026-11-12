import os
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from companion import Cue, Observation
from desktop import DesktopController, ListenJob
from profiles import load_settings


@pytest.fixture
def desktop(tmp_path, monkeypatch):
    import desktop as module

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(DesktopController, "connect_brain", lambda *args: None)
    controller = DesktopController(SimpleNamespace(confirm=lambda text: False), load_settings())
    controller.companion.timer.stop()
    controller.brain = SimpleNamespace(
        ready=True,
        voice_ready=False,
        speech_ready=False,
        companion_context="",
        cancelled=__import__("threading").Event(),
        companion_reply=lambda *_: "Elige un paso de dos minutos. ¿Cuál puedes hacer ahora?",
        _remember_turn=MagicMock(),
        status="idle",
    )
    yield controller
    controller.companion.close()
    controller.shutdown_timer.stop()
    for job in list(controller.jobs):
        job.wait(3000)
    controller.window.deleteLater()
    app.processEvents()


def test_no_foreground_title_read_outside_active_session(desktop, monkeypatch):
    import companion_runtime

    probe = MagicMock(return_value=Observation(title="youtube"))
    monkeypatch.setattr(companion_runtime, "foreground_observation", probe)
    monkeypatch.setattr(desktop.companion, "input_idle", lambda: 0)
    desktop.companion.tick()
    probe.assert_not_called()
    desktop.companion.start("programar", 25)
    desktop.companion.tick()
    assert probe.call_count == 1
    desktop.window.companion_panel.observe.setChecked(False)
    desktop.companion.tick()
    assert probe.call_count == 1
    assert not desktop.companion.focus.settings.observe_apps


def test_manual_support_runs_without_tool_loop_and_returns_ui_to_ready(desktop):
    desktop.companion.support()
    deadline = time.monotonic() + 3
    while desktop.busy and time.monotonic() < deadline:
        QTest.qWait(20)
    assert not desktop.busy
    assert "dos minutos" in desktop.window.companion_panel.advice.text()
    desktop.brain._remember_turn.assert_called_once()


def test_busy_defers_companion_speech_and_disabled_clears_deferred_message(desktop):
    desktop.busy = True
    desktop.companion.announce(Cue("start", "una tarea"))
    assert desktop.companion.deferred is not None
    desktop.window.companion_panel.enabled.setChecked(False)
    assert desktop.companion.deferred is None
    assert not desktop.companion.focus.settings.enabled


def test_camera_stays_off_until_explicit_toggle_and_stale_sample_is_ignored(desktop):
    assert not desktop.window.companion_panel.camera_enabled.isChecked()
    assert desktop.companion.presence_worker is None
    desktop.companion._presence({"present": True, "point": (0.5, 0)})
    assert desktop.companion.presence is None


@pytest.mark.parametrize("active", [True, False])
def test_voice_followup_allows_answer_without_wakeword_only_during_window(monkeypatch, active):
    from PySide6.QtTest import QSignalSpy

    import desktop as module

    brain = SimpleNamespace(transcribe=lambda wav: "mi siguiente paso es abrir mi proyecto")
    calls = 0

    def record(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            job.stop()
            return b""
        return b"wav"

    monkeypatch.setattr(module, "record_speech", record)
    job = ListenJob(brain, followup_until=time.monotonic() + (15 if active else -1))
    result = QSignalSpy(job.command)
    job.run()
    assert result.count() == (1 if active else 0)
    if active:
        assert result.at(0) == ["mi siguiente paso es abrir mi proyecto"]


@pytest.mark.parametrize("faces", [[], [(80, 60, 80, 80)]])
def test_camera_presence_emits_only_boolean_and_point_and_releases_capture(monkeypatch, faces):
    import cv2
    import numpy as np

    from attention import PresenceWorker

    camera, detector = MagicMock(), MagicMock()
    camera.isOpened.return_value = True
    camera.read.return_value = (True, np.zeros((240, 320, 3), dtype=np.uint8))
    detector.empty.return_value = False
    detector.detectMultiScale.return_value = faces
    monkeypatch.setattr(cv2, "VideoCapture", lambda *_: camera)
    monkeypatch.setattr(cv2, "CascadeClassifier", lambda *_: detector)
    worker = PresenceWorker()
    samples = []

    def consume(sample):
        samples.append(sample)
        worker.stop()

    worker.sample.connect(consume)
    worker.run()
    camera.release.assert_called_once()
    assert set(samples[0]) == {"present", "point"}
    assert samples[0]["present"] is bool(faces)
    assert samples[0]["point"] is None if not faces else len(samples[0]["point"]) == 2
