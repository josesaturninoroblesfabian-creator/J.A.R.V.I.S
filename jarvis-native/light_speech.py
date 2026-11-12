"""Offline Spanish recognition and Windows voices without Torch or GPU models."""

from __future__ import annotations

import io
import json
import threading
import wave
from types import SimpleNamespace

from app_paths import asset_path


class VoskSpeech:
    backend_id = "vosk-light"

    def __init__(self):
        from vosk import Model, SetLogLevel

        SetLogLevel(-1)
        path = asset_path("assets/vosk-model-small-es-0.42")
        if not (path / "am/final.mdl").exists():
            raise RuntimeError(
                "Falta el paquete de voz española. Reinstala Jarvis con voz incluida."
            )
        self._model = Model(str(path))
        self._lock = threading.Lock()

    def transcribe(self, audio, **_kwargs):
        from vosk import KaldiRecognizer

        with self._lock, wave.open(io.BytesIO(audio), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2:
                raise ValueError("La voz necesita audio mono de 16 bits.")
            recognizer = KaldiRecognizer(self._model, source.getframerate())
            # Feed in chunks: the recognizer remains bounded even with long speech.
            parts = []
            while data := source.readframes(4000):
                if recognizer.AcceptWaveform(data):
                    parts.append(json.loads(recognizer.Result()).get("text", ""))
            parts.append(json.loads(recognizer.FinalResult()).get("text", ""))
        return SimpleNamespace(text=" ".join(p for p in parts if p).strip())

    def close(self):
        self._model = None


class WindowsVoice:
    backend_id = "windows-sapi"

    def synthesize(self, text, *, speed=1.0, voice_id="", **_kwargs):
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            choices = list(voice.GetVoices())
            spanish = []
            for token in choices:
                try:
                    if int(token.GetAttribute("Language").split(";")[0], 16) & 0x3FF == 0x0A:
                        spanish.append(token)
                except Exception:
                    continue
            selected = next(
                (t for t in spanish if voice_id and voice_id.lower() in t.GetDescription().lower()),
                None,
            )
            selected = selected or next(
                (t for t in spanish if "raul" in t.GetDescription().lower()), None
            )
            if selected is not None:
                voice.Voice = selected
            elif spanish:
                voice.Voice = spanish[0]
            voice.Rate = max(-4, min(4, round((speed - 1) * 8)))
            voice.Volume = 90
            stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
            stream.Format.Type = 22  # 22.05 kHz, 16-bit mono PCM.
            voice.AudioOutputStream = stream
            voice.Speak(text)
            pcm = bytes(stream.GetData())
            voice = stream = None
        finally:
            pythoncom.CoUninitialize()
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(pcm)
        return SimpleNamespace(audio=output.getvalue())
