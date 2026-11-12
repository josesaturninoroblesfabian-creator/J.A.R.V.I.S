import struct
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openjarvis.core.config import JarvisConfig
from openjarvis.core.types import Message, Role, ToolCall

from brain import JarvisBrain, vision_request
from history import ConversationHistory
from profiles import load_settings, profile_config
from providers import GroqEngine
from voice import record_speech


@pytest.mark.parametrize(
    ("text", "source"),
    [
        ("Mi pantalla parpadea, ayúdame", None),
        ("Necesito programar una cámara", None),
        ("Mira la pantalla", "screen"),
        ("Describe lo que ves en la cámara", "camera"),
        ("/ver pantalla", "screen"),
        ("/ver camara", "camera"),
    ],
)
def test_capture_only_on_visual_request(text, source):
    assert vision_request(text) == source


def test_profile_does_not_mutate_sdk_config():
    original = JarvisConfig()
    original.intelligence.default_model = "existing-model"
    settings = load_settings(profile_name="local-fast")
    selected = profile_config(original, settings.profile)
    assert original.intelligence.default_model == "existing-model"
    assert selected.intelligence.default_model == "qwen3.5:2b"
    assert selected.engine.default == selected.intelligence.preferred_engine == "ollama"


def test_unknown_profile_is_not_silently_replaced():
    with pytest.raises(ValueError, match="Perfil desconocido"):
        load_settings(profile_name="does-not-exist")


def test_missing_credential_does_not_select_paid_fallback(monkeypatch):
    import credential_store

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(credential_store.CredentialStore, "load", lambda self, name: "")
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        load_settings(profile_name="groq").profile.validate_credentials()


def test_history_survives_restart_and_keeps_complete_turns(tmp_path):
    path = tmp_path / "history.db"
    first = ConversationHistory(path, max_messages=3)
    first.append_turn("primero", "respuesta uno")
    first.append_turn("segundo", "respuesta dos")
    restarted = ConversationHistory(path, max_messages=3)
    assert restarted.recent() == [("user", "segundo"), ("assistant", "respuesta dos")]


def test_history_character_budget_and_clear(tmp_path):
    history = ConversationHistory(tmp_path / "history.db", max_chars=12)
    history.append_turn("old", "old")
    history.append_turn("new", "answer")
    assert history.recent() == [("user", "new"), ("assistant", "answer")]
    history.clear()
    assert history.recent() == []


def test_history_releases_windows_file_handles(tmp_path):
    path = tmp_path / "history.db"
    history = ConversationHistory(path)
    history.append_turn("hola", "listo")
    assert history.recent()
    path.unlink()
    assert not path.exists()


def ready_brain(tmp_path):
    settings = load_settings(profile_name="local-fast")
    brain = JarvisBrain(settings=settings, data_dir=tmp_path)
    cfg = JarvisConfig()
    cfg.agent.context_from_memory = False
    brain._jarvis = SimpleNamespace(config=cfg)
    brain.model = "test-model"
    brain._agent = MagicMock()
    brain._agent.run.return_value = SimpleNamespace(content="hecho")
    brain.ready = True
    return brain


def test_task_and_conversation_share_history(tmp_path):
    brain = ready_brain(tmp_path)
    brain.ask("El proyecto se llama reactor")
    brain.ask("ahora crea su archivo de configuración")
    context = brain._agent.run.call_args.kwargs["context"]
    messages = context.conversation.messages
    assert messages[1].content == "El proyecto se llama reactor"
    assert messages[2].content == "hecho"
    assert "Fecha y hora reales" in messages[0].content


def test_failed_tool_run_is_not_replayed_or_remembered(tmp_path):
    brain = ready_brain(tmp_path)
    brain._agent.run.side_effect = RuntimeError("connection lost after tool execution")
    assert "No pude completar" in brain.ask("crea archivo")
    assert brain._agent.run.call_count == 1
    assert brain._history.recent() == []


def test_memory_failure_does_not_report_completed_action_as_failed(tmp_path):
    brain = ready_brain(tmp_path)
    brain._history.append_turn = MagicMock(side_effect=OSError("disk full"))
    assert brain.ask("crea un archivo") == "hecho"
    assert "historial" in brain.last_error
    assert brain._agent.run.call_count == 1


def test_vision_disabled_profile_never_captures(tmp_path):
    from dataclasses import replace

    settings = load_settings(profile_name="groq")
    settings = replace(settings, profile=replace(settings.profile, local_vision_model=""))
    brain = JarvisBrain(settings=settings, data_dir=tmp_path)
    brain._capture_camera_b64 = MagicMock(side_effect=AssertionError("must not capture"))
    assert "no tiene visión" in brain.ask_vision("mira la cámara")
    brain._capture_camera_b64.assert_not_called()


def test_screen_capture_stays_in_memory_on_engine_failure(tmp_path):
    brain = ready_brain(tmp_path)
    brain._desktop_driver = MagicMock()
    brain._desktop_driver.screenshot.return_value = (b"test-image", (1920, 1080))
    brain._prompt_builder = MagicMock()
    brain._prompt_builder.build.return_value = "persona"
    brain._jarvis._engine = MagicMock()
    brain._jarvis._engine.generate.side_effect = RuntimeError("offline")
    with pytest.raises(RuntimeError, match="offline"):
        brain.ask_vision("mira la pantalla", "screen")
    brain._desktop_driver.screenshot.assert_called_once_with()
    assert not list(tmp_path.glob("*.png"))


def test_screen_analysis_uses_current_image_without_old_chat_guesses(tmp_path):
    brain = ready_brain(tmp_path)
    brain._history.append_turn("archivo", "Una suposición antigua sobre archivo_inventado.tsx")
    brain._desktop_driver = MagicMock()
    brain._desktop_driver.screenshot.return_value = (b"test-image", (1920, 1080))
    brain._jarvis._engine = MagicMock()
    brain._jarvis._engine.generate.return_value = {"content": "Veo tu aplicación."}
    assert brain.ask_vision("mira la pantalla", "screen") == "Veo tu aplicación."
    messages = brain._jarvis._engine.generate.call_args.args[0]
    assert len(messages) == 2
    assert messages[-1].images
    assert all("archivo_inventado" not in message.text for message in messages)
    assert not list(tmp_path.glob("*.png"))


def test_groq_authentication_and_tool_call_roundtrip(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    engine = GroqEngine()
    captured = []

    def respond(request):
        import json

        captured.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "id": "resp-1",
                "object": "chat.completion",
                "created": 0,
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-2",
                                    "type": "function",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": '{"expression":"2+2"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    from openai import OpenAI

    engine._client.close()
    engine._client = OpenAI(
        api_key="test-key",
        base_url="https://api.groq.com/openai/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    try:
        messages = [
            Message(role=Role.USER, content="calcula"),
            Message(role=Role.ASSISTANT, tool_calls=[ToolCall("call-1", "think", "{}")]),
            Message(role=Role.TOOL, name="think", tool_call_id="call-1", content="ok"),
        ]
        result = engine.generate(messages, model="openai/gpt-oss-120b")
        assert result["tool_calls"][0]["name"] == "calculator"
        assert captured[0]["messages"][-1]["tool_call_id"] == "call-1"
        assert "name" not in captured[0]["messages"][-1]
    finally:
        engine.close()


def test_groq_429_is_not_retried_without_bound(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    engine = GroqEngine()
    from openai import OpenAI

    from provider_errors import ProviderBusy

    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(429, json={"error": {"message": "quota exhausted"}})

    engine._client.close()
    engine._client = OpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    try:
        with pytest.raises(ProviderBusy):
            engine.generate([Message(role=Role.USER, content="hola")], model="test")
        assert len(requests) == 1
    finally:
        engine.close()


@pytest.mark.parametrize("speech", [False, True])
def test_microphone_discards_silence(monkeypatch, speech):
    import sounddevice

    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.read.return_value = (struct.pack("1024h", *([1000 if speech else 0] * 1024)), False)
    monkeypatch.setattr(sounddevice, "RawInputStream", lambda **kwargs: stream)
    audio = record_speech()
    assert bool(audio) is speech
    if speech:
        assert audio.startswith(b"RIFF")


def test_microphone_stop_cancels_recording(monkeypatch):
    import threading

    import sounddevice

    stop = threading.Event()
    stop.set()
    stream = MagicMock()
    monkeypatch.setattr(sounddevice, "RawInputStream", lambda **kwargs: stream)
    assert record_speech(stop) == b""


def test_native_module_is_importable_without_logging_to_user_home(tmp_path, monkeypatch):
    # GUI import should not start the event loop, open microphone, or create logs.
    import os

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    import jarvis_native

    assert callable(jarvis_native.main)
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
