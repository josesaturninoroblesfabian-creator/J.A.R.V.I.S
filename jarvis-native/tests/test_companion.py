from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from companion import (
    CompanionSettings,
    CompanionStore,
    FocusCompanion,
    Observation,
    companion_command,
)
from credential_store import CredentialStore


@pytest.fixture
def focus(tmp_path):
    service = FocusCompanion(CompanionStore(tmp_path / "coach.db"), clock=lambda: 0)
    service.start("terminar mi función", 25, now=0)
    return service


def advance(focus, observation, until, **kwargs):
    cue = None
    for now in range(int(focus.last_tick) + 5, until + 1, 5):
        cue = focus.tick(observation, now=now, hour=12, **kwargs) or cue
    return cue


def test_ocio_needs_sustained_evidence_and_not_every_window_change(focus):
    work = Observation(app="code.exe", title="mi proyecto")
    ocio = Observation(app="chrome.exe", title="YouTube")
    assert advance(focus, work, 20) is None
    assert advance(focus, ocio, 50) is None
    assert advance(focus, work, 55) is None
    assert advance(focus, ocio, 105).kind == "distraction"


def test_work_exception_prevents_nudge_and_titles_are_not_stored(focus):
    focus.configure(replace(focus.settings, allowed="tutorial python"))
    sample = Observation(app="chrome.exe", title="tutorial python YouTube private secret page")
    assert advance(focus, sample, 300) is None
    focus.store.event(focus.start("programar", 25, now=300))
    raw = focus.store.path.read_bytes()
    assert b"private secret page" not in raw


def test_cooldown_and_snooze_bound_the_number_of_interruptions(focus):
    ocio = Observation(title="tiktok")
    assert advance(focus, ocio, 50).kind == "distraction"
    assert advance(focus, ocio, 150) is None
    assert advance(focus, ocio, 235).kind == "distraction"
    focus.snooze(now=235)
    assert advance(focus, ocio, 830) is None
    assert advance(focus, ocio, 885).kind == "distraction"


def test_quiet_hours_work_across_midnight_and_never_generate_cues(focus):
    for now in range(5, 100, 5):
        assert focus.tick(Observation(title="youtube"), now=now, hour=23) is None
    assert focus.settings.quiet(23)
    assert focus.settings.quiet(7)
    assert not focus.settings.quiet(12)
    assert not replace(focus.settings, quiet_start=0, quiet_end=0).quiet(3)


def test_pause_lock_and_system_sleep_are_not_counted_as_focus(focus):
    advance(focus, Observation(), 20)
    focus.toggle_pause(now=20)
    advance(focus, Observation(title="youtube"), 100)
    assert focus.elapsed == 20
    focus.toggle_pause(now=100)
    focus.tick(Observation(locked=True), now=110, hour=12)
    assert focus.elapsed == 20
    focus.tick(Observation(), now=500, hour=12)
    assert focus.elapsed == 20


def test_busy_queues_nudge_but_discards_it_if_user_returns_to_work(focus):
    ocio = Observation(title="tiktok")
    assert advance(focus, ocio, 60, can_interrupt=False) is None
    assert focus.pending.kind == "distraction"
    assert focus.tick(Observation(title="code"), now=65, hour=12) is None
    assert focus.pending is None


def test_focus_to_break_and_return_execute_once_and_save_minutes(focus):
    focus.start("estudiar", 1, now=0)
    cue = advance(focus, Observation(), 60)
    assert cue.kind == "break"
    assert focus.phase == "break"
    assert focus.store.summary() == {"sessions": 1, "minutes": 1}
    assert advance(focus, Observation(), 65) is None
    assert advance(focus, Observation(), 360).kind == "return"
    assert focus.phase == "ready"


def test_idle_or_absence_suggests_pause_without_accusing_distraction(focus):
    cue = advance(focus, Observation(idle_seconds=400), 70)
    assert cue.kind == "away"
    assert "leyendo" in cue.text
    assert focus.nudges == 0


def test_disabled_app_observer_never_uses_titles(focus):
    focus.configure(replace(focus.settings, observe_apps=False))
    focus.classify = MagicMock(side_effect=AssertionError("must not inspect"))
    assert advance(focus, Observation(title="youtube"), 100) is None
    focus.classify.assert_not_called()


def test_proactive_off_does_not_disable_manual_focus_timer(focus):
    focus.configure(replace(focus.settings, enabled=False))
    focus.start("leer", 1, now=0)
    assert advance(focus, Observation(title="youtube"), 60) is None
    assert focus.phase == "break"
    assert focus.store.summary()["sessions"] == 1


def test_finished_session_does_not_count_as_completed_and_restart_keeps_preferences(focus):
    focus.configure(replace(focus.settings, style="suave"))
    advance(focus, Observation(), 20)
    focus.finish()
    restarted = CompanionStore(focus.store.path)
    assert restarted.summary()["sessions"] == 0
    assert restarted.settings().style == "suave"


@pytest.mark.parametrize(
    "text,action",
    [
        ("inicia enfoque de 25 minutos para programar", "start"),
        ("Jarvis, pausa el enfoque", "pause"),
        ("reanuda la sesión", "resume"),
        ("termina la sesión", "finish"),
        ("no me interrumpas por 10 minutos", "snooze"),
        ("me distraje", "support"),
        ("el algoritmo de enfoque falla", None),
        ("no inicies enfoque", None),
    ],
)
def test_companion_commands_require_explicit_intent(text, action):
    result = companion_command(text)
    assert (result[0] if result else None) == action


@pytest.mark.parametrize(
    "field,value",
    [("work_minutes", 0), ("quiet_start", 24), ("style", "humillar"), ("spoken", "yes")],
)
def test_invalid_settings_rejected(field, value):
    with pytest.raises(ValueError):
        replace(CompanionSettings(), **{field: value}).validate()


def test_dpapi_round_trip_is_not_plaintext_and_cannot_escape_directory(tmp_path):
    store = CredentialStore(tmp_path / "keys")
    secret = "fake-key-for-a-local-test-only"
    store.save("GROQ_API_KEY", secret)
    assert store.load("GROQ_API_KEY") == secret
    assert secret.encode() not in (tmp_path / "keys" / "GROQ_API_KEY.dpapi").read_bytes()
    with pytest.raises(ValueError):
        store.load("../other")


def test_hybrid_groq_keeps_captured_images_on_local_engine(tmp_path):
    from types import SimpleNamespace

    from brain import JarvisBrain
    from profiles import load_settings
    from progress_engine import ProgressEngine

    settings = replace(load_settings(profile_name="groq"), allow_local_vision=True)
    brain = JarvisBrain(settings=settings, data_dir=tmp_path)
    local, cloud = MagicMock(), MagicMock()
    local.generate.return_value = {"content": "Veo la interfaz de Jarvis."}
    brain._jarvis = SimpleNamespace(_engine=cloud, close=MagicMock())
    brain._desktop_driver = MagicMock()
    brain._desktop_driver.screenshot.return_value = (b"private-image", (1920, 1080))
    brain._local_visual_engine = local
    brain._local_visual_progress = ProgressEngine(local, brain.cancelled)
    try:
        assert brain.ask_vision("mira la pantalla", "screen") == "Veo la interfaz de Jarvis."
        cloud.generate.assert_not_called()
        assert local.generate.call_args.kwargs["model"] == "qwen3.5:9b"
        assert local.generate.call_args.args[0][-1].images
    finally:
        brain.close()


def test_companion_support_does_not_run_agent_or_request_any_tools(tmp_path):
    from brain import JarvisBrain
    from profiles import load_settings

    brain = JarvisBrain(settings=load_settings(profile_name="local-fast"), data_dir=tmp_path)
    brain.model = "test-model"
    brain._agent = MagicMock()
    brain._progress_engine = MagicMock()
    brain._progress_engine.generate.return_value = {"content": "Un paso pequeño cuenta."}
    brain.companion_context = "Meta: escribir una función."
    assert brain.companion_reply("me distraje") == "Un paso pequeño cuenta."
    brain._agent.run.assert_not_called()
    assert "tools" not in brain._progress_engine.generate.call_args.kwargs
    assert brain._progress_engine.on_text is None
