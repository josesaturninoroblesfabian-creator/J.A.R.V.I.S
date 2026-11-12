"""Offline executable self-test: imports, tools, writable data, speech and resources."""

import io
import json
import sys
import time
import traceback
import wave
from dataclasses import replace
from pathlib import Path


def run(report_path):
    result = {"ok": False, "network_used": False}
    brain = None
    try:
        import psutil
        from openjarvis.core.registry import EngineRegistry
        from openjarvis.core.types import ToolCall
        from openjarvis.engine._stubs import InferenceEngine

        from app_paths import data_dir
        from brain import JarvisBrain
        from light_speech import VoskSpeech, WindowsVoice
        from profiles import Profile, load_settings

        class DiagnosticEngine(InferenceEngine):
            engine_id = "diagnostic"

            def generate(self, *args, **kwargs):
                return {"content": "Listo", "usage": {}}

            async def stream(self, *args, **kwargs):
                yield "Listo"

            def list_models(self):
                return ["diagnostic"]

            def health(self):
                return True

            def can_serve(self, model):
                return True

        EngineRegistry.register_value("diagnostic", DiagnosticEngine)
        settings = replace(
            load_settings(),
            profile=Profile("diagnostic", "Prueba local", "diagnostic", "diagnostic"),
        )
        brain = JarvisBrain(settings=settings, data_dir=data_dir() / "self-test")
        brain.init(initialize_voice=False)
        calculation = brain._agent._executor.execute(
            ToolCall("test-calculator", "calculator", '{"expression":"137*29"}')
        )
        if not calculation.success or "3973" not in calculation.content:
            raise RuntimeError("La calculadora no superó la prueba")
        start = time.perf_counter()
        audio = WindowsVoice().synthesize("Hola. Estoy aquí para ayudarte.").audio
        with wave.open(io.BytesIO(audio)) as source:
            duration = source.getnframes() / source.getframerate()
        recognizer = VoskSpeech()
        result.update(
            {
                "ok": True,
                "calculator": calculation.content,
                "tools": brain._available_tool_names,
                "speech_load_seconds": round(time.perf_counter() - start, 2),
                "speech_audio_seconds": round(duration, 2),
                "rss_mb": round(psutil.Process().memory_info().rss / 2**20, 1),
                "torch_loaded": "torch" in sys.modules,
                "whisper_loaded": "faster_whisper" in sys.modules,
            }
        )
        recognizer.close()
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        if brain:
            brain.close()
    report = Path(report_path).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
