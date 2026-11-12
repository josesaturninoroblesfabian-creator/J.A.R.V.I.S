import os
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import httpx
import pytest
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from desktop import JarvisWindow, ListenJob, spoken_reply, wake_command
from profiles import load_settings
from runtime_support import SingleInstance, ensure_ollama, local_engine_url


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_spoken_reply_omits_markup_and_code(app):
    reply = "## Listo\n**Abrí** [la guía](https://example.com).\n\n```py\nprint('test')\n```"
    assert spoken_reply(reply) == "Listo Abrí la guía. El código está en la conversación."


@pytest.mark.parametrize(
    ("text", "require_wake", "expected"),
    [
        ("Jarvis, calcula 2 + 2", True, "calcula 2 + 2"),
        ("Yarvis abre la interfaz", True, "abre la interfaz"),
        ("Carbis cambia el holograma a rojo", True, "cambia el holograma a rojo"),
        ("el jarvisiano", True, None),
        ("hola", False, "hola"),
        ("Jarvis", True, ""),
    ],
)
def test_wake_word_and_single_listen(text, require_wake, expected):
    assert wake_command(text, require_wake=require_wake) == expected


def test_spanish_window_sends_text_and_has_actual_audio_controls(app, tmp_path, monkeypatch):
    import desktop

    monkeypatch.setattr(desktop, "DATA_DIR", tmp_path)
    window = JarvisWindow(load_settings())
    try:
        window.set_busy(False)
        spy = QSignalSpy(window.submit)
        window.input.setPlainText("hola Jarvis")
        window.send.click()
        assert spy.count() == 1
        assert spy.at(0) == ["hola Jarvis"]
        assert window.nav[1].text() == "Voz y micrófono"
        assert window.test_button.text() == "Probar voz en español"
        assert window.microphone.count() >= 1
        assert window.speaker.count() >= 1
        window.append_message("assistant", "<script>alert(1)</script>")
        assert "<script>" in window.conversation.toPlainText()
    finally:
        window.deleteLater()
        app.processEvents()


def test_single_instance_does_not_start_second_desktop(app, tmp_path):
    first, second = SingleInstance(tmp_path), SingleInstance(tmp_path)
    try:
        assert first.acquire()
        assert not second.acquire()
    finally:
        second.close()
        first.close()


def test_exit_button_and_window_close_request_shutdown(app, tmp_path, monkeypatch):
    import desktop

    monkeypatch.setattr(desktop, "DATA_DIR", tmp_path)
    window = JarvisWindow(load_settings())
    try:
        spy = QSignalSpy(window.exit_requested)
        window.exit_button.click()
        window.close()
        assert spy.count() == 2
    finally:
        window.deleteLater()
        app.processEvents()


def test_hidden_hologram_stops_its_animation(app):
    from jarvis_native import CosmicBubble

    bubble = CosmicBubble(SimpleNamespace(status="idle"), lambda: None)
    try:
        bubble.show()
        assert bubble._timer.isActive()
        bubble.hide()
        assert not bubble._timer.isActive()
    finally:
        bubble.deleteLater()
        app.processEvents()


def test_ollama_normalizes_loopback_without_changing_remote_url():
    assert local_engine_url("") == "http://127.0.0.1:11434"
    assert local_engine_url("http://localhost:11434") == "http://127.0.0.1:11434"
    assert local_engine_url("https://my-server:11434") == "https://my-server:11434"


def test_running_ollama_is_reused_not_started_again(monkeypatch):
    import runtime_support

    client = MagicMock()
    client.__enter__.return_value = client
    client.get.return_value = httpx.Response(200, json={"models": []})
    monkeypatch.setattr(runtime_support.httpx, "Client", MagicMock(return_value=client))
    start = MagicMock(side_effect=AssertionError("must reuse existing server"))
    monkeypatch.setattr(runtime_support.subprocess, "Popen", start)
    ensure_ollama("http://localhost:11434")
    start.assert_not_called()


def test_ollama_recovers_when_server_was_not_running(monkeypatch):
    import runtime_support

    client = MagicMock()
    client.__enter__.return_value = client
    client.get.side_effect = [
        httpx.ConnectError("offline"),
        httpx.Response(200, json={"models": []}),
    ]
    monkeypatch.setattr(runtime_support.httpx, "Client", MagicMock(return_value=client))
    monkeypatch.setattr(runtime_support.shutil, "which", lambda name: "ollama.exe")
    start = MagicMock()
    monkeypatch.setattr(runtime_support.subprocess, "Popen", start)
    ensure_ollama("http://127.0.0.1:11434")
    assert start.call_count == 1
    assert start.call_args.args[0] == ["ollama.exe", "serve"]


def test_single_listen_does_not_require_wake_word(app, monkeypatch):
    import desktop

    brain = SimpleNamespace(transcribe=lambda wav: "calcula dos más dos")
    monkeypatch.setattr(desktop, "record_speech", lambda *args, **kwargs: b"wav")
    job = ListenJob(brain, once=True)
    result = QSignalSpy(job.command)
    job.run()
    assert result.at(0) == ["calcula dos más dos"]
