from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from brain import JarvisBrain, needs_tools
from camera_device import open_camera
from companion import companion_command
from credential_store import credential_error
from profiles import load_settings
from provider_errors import ProviderBusy, retry_delay
from providers import GroqEngine


@pytest.mark.parametrize("text", ["enciende la cámara", "prende mi cámara", "activa la webcam"])
def test_camera_enable_is_a_local_command_and_not_a_cloud_tool(text):
    assert companion_command(text)[0] == "camera_on"


@pytest.mark.parametrize("text", ["apaga la cámara", "cierra mi webcam"])
def test_camera_disable_is_local(text):
    assert companion_command(text)[0] == "camera_off"


@pytest.mark.parametrize(
    "spoken,minutes", [("veinticinco", 25), ("treinta y cinco", 35), ("un", 1)]
)
def test_spoken_focus_minutes_are_understood(spoken, minutes):
    action, parameters = companion_command(
        f"inicia una sesión de enfoque durante {spoken} minutos para programar"
    )
    assert action == "start"
    assert parameters["minutes"] == minutes


def test_camera_fallback_releases_failed_backend_before_next_attempt(monkeypatch):
    import cv2

    bad, good = MagicMock(), MagicMock()
    bad.isOpened.return_value = False
    good.isOpened.return_value = True
    good.read.return_value = (True, MagicMock())
    create = MagicMock(side_effect=[bad, good])
    monkeypatch.setattr(cv2, "VideoCapture", create)
    capture, frame, method = open_camera(1)
    assert capture is good and method == "msmf"
    bad.release.assert_called_once()
    assert create.call_args_list[0].args[0] == 1


@pytest.mark.parametrize(
    "text,tools",
    [
        ("hola, cómo estás", False),
        ("gracias por acompañarme", False),
        ("crea un archivo", True),
        ("calcula 12*4", True),
        ("busca información actual", True),
    ],
)
def test_casual_conversation_does_not_send_all_tool_definitions(text, tools):
    assert needs_tools(text) is tools


def test_rate_limit_wait_is_taken_from_header_not_invented():
    error = SimpleNamespace(response=SimpleNamespace(headers={"retry-after": "6.25"}))
    assert retry_delay(error) == 6.25
    assert "org_" not in credential_error(ProviderBusy(6.25))


def test_429_retries_only_the_same_http_request_once(monkeypatch):
    from openai import OpenAI

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    engine = GroqEngine()
    requests = []

    def respond(request):
        requests.append(request.content)
        if len(requests) == 1:
            return httpx.Response(
                429, headers={"retry-after": "0.001"}, json={"error": {"message": "wait"}}
            )
        return httpx.Response(
            200,
            json={
                "id": "ok",
                "model": "test",
                "created": 0,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "listo"},
                    }
                ],
            },
        )

    engine._client.close()
    engine._client = OpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    try:
        assert engine.generate([], model="test")["content"] == "listo"
        assert requests[0] == requests[1]
        assert len(requests) == 2
    finally:
        engine.close()


def test_light_voice_does_not_initialize_neural_backends(tmp_path):
    brain = JarvisBrain(settings=load_settings(), data_dir=tmp_path)
    brain._init_voice()
    try:
        assert brain._tts.backend_id == "windows-sapi"
        assert brain._stt.backend_id == "vosk-light"
        assert brain.voice_ready
    finally:
        brain.close()


def test_visual_model_is_not_loaded_automatically_in_light_mode(tmp_path):
    brain = JarvisBrain(
        settings=replace(load_settings(profile_name="groq"), allow_local_vision=False),
        data_dir=tmp_path,
    )
    brain._local_visual_engine = None
    with pytest.raises(RuntimeError, match="ahorrar recursos"):
        brain._vision_backend()
    assert brain._local_visual_engine is None
