import asyncio
import json
import sqlite3
import threading
from unittest.mock import MagicMock

import pytest
from openjarvis.engine._stubs import StreamChunk

from appearance import PALETTE, AppearanceStore
from history import ConversationHistory
from native_tools import DesktopAccess, DesktopDriver, DesktopTool, HologramTool, send_unicode
from progress_engine import ProgressEngine, RequestCancelled
from scheduling import NativeSchedules, ScheduleAdapter


def test_hologram_tool_persists_real_color_and_rejects_invalid_input(tmp_path):
    file = tmp_path / "hologram.json"
    appearance = AppearanceStore(file)
    tool = HologramTool(appearance)
    assert tool.execute(color="rojo", state="listening").success
    assert json.loads(file.read_text())["listening"] == "#F36F83"
    assert AppearanceStore(file).colors()["listening"] == "#F36F83"
    assert not tool.execute(color="not-a-color").success
    assert appearance.colors()["thinking"] == PALETTE["thinking"]


def test_existing_history_migrates_without_losing_messages(tmp_path):
    file = tmp_path / "history.db"
    db = sqlite3.connect(file)
    db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, role TEXT, content TEXT)")
    db.executemany(
        "INSERT INTO messages(role,content) VALUES (?,?)",
        [("user", "hola"), ("assistant", "listo")],
    )
    db.commit()
    db.close()
    history = ConversationHistory(file)
    assert history.recent() == [("user", "hola"), ("assistant", "listo")]
    original = history.active_id
    new = history.create()
    assert history.recent() == []
    history.append_turn("nuevo", "respuesta")
    history.activate(original)
    assert history.recent()[0][1] == "hola"
    history.activate(new)
    assert history.recent()[0][1] == "nuevo"


def test_desktop_pause_prevents_any_driver_action():
    access = DesktopAccess()
    access.enabled = False
    driver = DesktopDriver(access)
    result = DesktopTool(driver).execute(action="move", x=100, y=100)
    assert not result.success
    assert "pausa" in result.content


def test_desktop_action_arguments_reach_driver_without_model_invention():
    driver = MagicMock()
    driver.perform.return_value = {"x": 500, "y": 300}
    result = DesktopTool(driver).execute(action="move", x=500, y=300)
    driver.perform.assert_called_once_with("move", x=500, y=300)
    assert result.success


def test_unicode_typing_encodes_accented_keys_without_using_clipboard():
    units, flags = [], []

    def fake_send(count, packets, size):
        assert size == 40  # Windows x64 INPUT layout, including the mouse union.
        for packet in packets:
            units.append(packet.payload.keyboard.scan)
            flags.append(packet.payload.keyboard.flags)
        return count

    send_unicode("español, acción", send_input=fake_send)
    raw = b"".join(unit.to_bytes(2, "little") for unit in units[::2])
    assert raw.decode("utf-16-le") == "español, acción"
    assert flags == [4, 6] * len("español, acción")


def test_stream_keeps_tool_arguments_and_progress():
    class FakeEngine:
        async def stream_full(self, messages, **kwargs):
            yield StreamChunk(content="Hola")
            yield StreamChunk(content=" mundo")
            yield StreamChunk(
                tool_calls=[
                    {
                        "index": 0,
                        "id": "call-1",
                        "function": {"name": "calculator", "arguments": '{"expression":'},
                    }
                ]
            )
            yield StreamChunk(tool_calls=[{"index": 0, "function": {"arguments": '"2+2"}'}}])
            yield StreamChunk(finish_reason="tool_calls", usage={"completion_tokens": 3})

    engine = ProgressEngine(FakeEngine(), threading.Event())
    progress = []
    engine.on_text = progress.append
    try:
        result = engine.generate([], model="test")
        assert progress == ["", "Hola", "Hola mundo"]
        assert result["tool_calls"][0] == {
            "id": "call-1",
            "name": "calculator",
            "arguments": '{"expression":"2+2"}',
        }
        assert result["usage"]["completion_tokens"] == 3
    finally:
        engine.shutdown()


def test_cancel_interrupts_waiting_stream():
    class SlowEngine:
        async def stream_full(self, messages, **kwargs):
            await asyncio.sleep(60)
            yield StreamChunk(content="too late")

    engine = ProgressEngine(SlowEngine(), threading.Event())
    engine.on_text = lambda text: None
    timer = threading.Timer(0.1, engine.cancel)
    timer.start()
    try:
        with pytest.raises(RequestCancelled):
            engine.generate([], model="test")
    finally:
        timer.cancel()
        engine.shutdown()


def test_scheduled_job_has_real_executor_and_closes_its_own_brain():
    brain = MagicMock()
    brain.ask.return_value = "terminado"
    adapter = ScheduleAdapter(lambda: brain)
    assert adapter.ask("revisar un proyecto") == "terminado"
    brain.init.assert_called_once_with(initialize_voice=False)
    brain._history.create.assert_called_once()
    brain.close.assert_called_once()
    assert not adapter.active.is_set()


def test_schedule_failure_is_logged_and_task_can_be_paused(tmp_path):
    brain = MagicMock()
    brain.ask.side_effect = RuntimeError("model offline")
    service = NativeSchedules(tmp_path / "tasks.db", lambda: brain)
    try:
        task = service.create("revisa el proyecto", 3600)
        service.scheduler._execute_task(task)
        rows = service.list()
        assert not rows[0][1][0]["success"]
        assert "offline" in rows[0][1][0]["error"]
        service.toggle(task.id)
        assert service.list()[0][0].status == "paused"
    finally:
        service.close()
