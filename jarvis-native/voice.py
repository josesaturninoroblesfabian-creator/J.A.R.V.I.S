"""Microphone and speech text helpers, independent of Qt."""

import logging

log = logging.getLogger("jarvis")
MIC_THRESHOLD = 250


def record_speech(
    stop_event=None,
    *,
    device=None,
    on_level=None,
    threshold=MIC_THRESHOLD,
    silence_seconds=0.9,
    startup_seconds=4.0,
):
    """Graba desde el micrófono hasta detectar silencio, con diagnóstico en el log."""
    import io
    import struct
    import wave

    import sounddevice as sd

    CHUNK = 1024
    SR = 16000
    silence_chunks = max(1, int(silence_seconds * SR / CHUNK))
    startup_chunks = max(1, int(startup_seconds * SR / CHUNK))
    max_chunks = int(30.0 * SR / CHUNK)

    frames = []
    silence_count = 0
    has_speech = False
    max_rms = 0.0
    with sd.RawInputStream(
        device=device, samplerate=SR, channels=1, dtype="int16", blocksize=CHUNK
    ) as stream:
        for chunk_index in range(max_chunks):
            if stop_event is not None and stop_event.is_set():
                return b""
            raw, _ = stream.read(CHUNK)
            data = bytes(raw)
            frames.append(data)
            n = len(data) // 2
            if n == 0:
                continue
            shorts = struct.unpack(f"{n}h", data[: n * 2])
            rms = (sum(s * s for s in shorts) / n) ** 0.5
            max_rms = max(max_rms, rms)
            if on_level is not None and len(frames) % 4 == 0:
                on_level(min(100, int(rms / 30)))
            if rms > threshold:
                if not has_speech:
                    # Keep ~0.4 s of pre-roll, not several seconds of startup silence.
                    frames = frames[-6:]
                has_speech = True
                silence_count = 0
            elif not has_speech and chunk_index + 1 >= startup_chunks:
                break
            elif has_speech:
                silence_count += 1
                if silence_count >= silence_chunks:
                    break
    logger = log.info if has_speech else log.debug
    logger("mic max_rms=%.0f speech=%s frames=%d", max_rms, has_speech, len(frames))
    if not has_speech:
        return b""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(b"".join(frames))
    return buf.getvalue()


def play_audio(audio: bytes, *, device=None):
    import io

    import sounddevice as sd
    import soundfile as sf

    samples, rate = sf.read(io.BytesIO(audio), dtype="float32")
    sd.play(samples, samplerate=rate, device=device)
    sd.wait()


def clean_for_speech(text: str) -> str:
    """Quita Markdown (asteriscos, negritas, listas) para que la voz suene natural."""
    import re

    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **negrita**
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)  # *cursiva*
    text = re.sub(r"__([^_]+)__", r"\1", text)  # __subrayado__
    text = re.sub(r"`([^`]+)`", r"\1", text)  # `código`
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # [enlace](url)
    text = re.sub(r"^\s*(#{1,6}\s+|\*\s+|[-*]\s+|\d+\.\s+)", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
