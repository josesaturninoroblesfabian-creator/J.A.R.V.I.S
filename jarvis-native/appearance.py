"""Persistent hologram palette shared by settings, tools and the overlay."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

PALETTE = {
    "boot": "#F2B75D",
    "voice": "#F2B75D",
    "idle": "#58D6F3",
    "listening": "#56E0A0",
    "transcribing": "#41CBBF",
    "thinking": "#AB8CFF",
    "tool": "#FFAB58",
    "speaking": "#67A4FF",
    "error": "#F36F83",
    "paused": "#8090A8",
}
STATE_LABELS = {
    "idle": "En espera",
    "listening": "Escuchando",
    "transcribing": "Reconociendo voz",
    "thinking": "Pensando",
    "tool": "Usando herramientas",
    "speaking": "Hablando",
    "error": "Error",
    "boot": "Iniciando",
    "voice": "Preparando voz",
    "paused": "En pausa",
}
COLORS = {
    "rojo": "#F36F83",
    "roja": "#F36F83",
    "verde": "#56E0A0",
    "azul": "#67A4FF",
    "morado": "#AB8CFF",
    "morada": "#AB8CFF",
    "violeta": "#AB8CFF",
    "naranja": "#FFAB58",
    "amarillo": "#FFD36D",
    "amarilla": "#FFD36D",
    "rosa": "#F38CCB",
    "rosado": "#F38CCB",
    "blanco": "#E9F4FF",
    "blanca": "#E9F4FF",
    "cian": "#58D6F3",
    "turquesa": "#41CBBF",
}


class AppearanceStore:
    def __init__(self, path: Path, on_change=None):
        self.path = path
        self.on_change = on_change
        self._lock = threading.RLock()
        self._colors = dict(PALETTE)
        self._preview = None
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            self._colors.update({k: self.normalize(v) for k, v in values.items() if k in PALETTE})
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    @staticmethod
    def normalize(color):
        color = COLORS.get(str(color).lower().strip(), str(color).strip())
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Usa un color como rojo, azul, verde o un código #RRGGBB.")
        return color.upper()

    def colors(self):
        with self._lock:
            return dict(self._colors)

    def color(self, state):
        with self._lock:
            if self._preview and time.monotonic() < self._preview[1]:
                return self._preview[0]
            return self._colors.get(state, self._colors["idle"])

    def set(self, state, color):
        if state not in PALETTE:
            raise ValueError(f"Estado desconocido: {state}")
        color = self.normalize(color)
        with self._lock:
            colors = {**self._colors, state: color}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(colors, indent=2), encoding="utf-8")
            temporary.replace(self.path)
            self._colors = colors
            self._preview = (color, time.monotonic() + 4)
        if self.on_change:
            self.on_change()
        return color
