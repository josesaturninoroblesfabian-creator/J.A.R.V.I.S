"""Tools for Jarvis's own interface and the local desktop."""

from __future__ import annotations

import io
import json
import threading

from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

from appearance import PALETTE, STATE_LABELS


def send_unicode(text, *, send_input=None, check=None):
    """Type UTF-16 through Windows input events; never replace the clipboard."""
    import ctypes
    from ctypes import wintypes

    class Keyboard(ctypes.Structure):
        _fields_ = [
            ("vk", wintypes.WORD),
            ("scan", wintypes.WORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("extra", ctypes.c_size_t),
        ]

    class Mouse(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("data", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("extra", ctypes.c_size_t),
        ]

    class Hardware(ctypes.Structure):
        _fields_ = [("message", wintypes.DWORD), ("low", wintypes.WORD), ("high", wintypes.WORD)]

    class Payload(ctypes.Union):
        _fields_ = [("keyboard", Keyboard), ("mouse", Mouse), ("hardware", Hardware)]

    class Input(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("payload", Payload)]

    if send_input is None:
        send_input = ctypes.WinDLL("user32", use_last_error=True).SendInput
        send_input.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
        send_input.restype = wintypes.UINT
    raw = text.encode("utf-16-le")
    packets = []
    for offset in range(0, len(raw), 2):
        unit = int.from_bytes(raw[offset : offset + 2], "little")
        for flags in (0x0004, 0x0006):  # UNICODE, then UNICODE | KEYUP.
            packets.append(Input(1, Payload(keyboard=Keyboard(0, unit, flags, 0, 0))))
    for offset in range(0, len(packets), 64):
        if check:
            check()
        group = packets[offset : offset + 64]
        events = (Input * len(group))(*group)
        if send_input(len(group), events, ctypes.sizeof(Input)) != len(group):
            raise RuntimeError("Windows no permitió escribir en la ventana activa.")


class HologramTool(BaseTool):
    tool_id = "hologram_configure"

    def __init__(self, appearance):
        self.appearance = appearance

    @property
    def spec(self):
        return ToolSpec(
            name=self.tool_id,
            category="interfaz",
            description=(
                "Cambia de verdad el color del holograma de Jarvis. "
                "Usa idle para el color base; listening al escuchar; thinking al pensar. "
                "No edites el código para cambiar colores."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "color": {"type": "string", "description": "rojo, verde, azul o #RRGGBB"},
                    "state": {"type": "string", "enum": list(PALETTE), "default": "idle"},
                },
                "required": ["color"],
            },
        )

    def execute(self, **params):
        try:
            state = params.get("state", "idle")
            color = self.appearance.set(state, params.get("color", ""))
            return ToolResult(
                tool_name=self.tool_id,
                success=True,
                content=(
                    f"Color del holograma actualizado a {color} para {STATE_LABELS[state]}. "
                    "Se muestra una vista previa de 4 segundos y la configuración queda guardada."
                ),
            )
        except (ValueError, OSError) as exc:
            return ToolResult(tool_name=self.tool_id, success=False, content=str(exc))


class DesktopAccess:
    def __init__(self):
        self.enabled = True
        self.stopped = threading.Event()

    def check(self):
        if not self.enabled or self.stopped.is_set():
            raise RuntimeError("El control de pantalla está en pausa. Actívalo en Herramientas.")


class DesktopDriver:
    def __init__(self, access):
        self.access = access

    def perform(self, action, **params):
        self.access.check()
        import pyautogui as gui

        gui.FAILSAFE = True
        gui.PAUSE = 0.1
        if action == "inspect":
            size, position = gui.size(), gui.position()
            import pygetwindow

            return {
                "width": size.width,
                "height": size.height,
                "cursor": {"x": position.x, "y": position.y},
                "active_window": pygetwindow.getActiveWindowTitle(),
                "windows": [t for t in pygetwindow.getAllTitles() if t][:30],
            }
        if action in {"move", "click", "double_click"}:
            x, y = int(params["x"]), int(params["y"])
            if not gui.onScreen(x, y):
                raise ValueError("Las coordenadas están fuera de la pantalla principal.")
            if action == "move":
                gui.moveTo(x, y, duration=0.25)
            else:
                button = params.get("button", "left")
                if button not in {"left", "right", "middle"}:
                    raise ValueError("Botón de ratón inválido")
                gui.click(
                    x, y, clicks=2 if action == "double_click" else 1, interval=0.12, button=button
                )
            return {"action": action, "x": x, "y": y}
        if action == "scroll":
            amount = max(-20, min(20, int(params.get("amount", 0))))
            gui.scroll(amount)
            return {"scrolled": amount}
        if action == "press":
            keys = [key.strip().lower() for key in params.get("keys", "").split("+")]
            if not 1 <= len(keys) <= 4 or any(key not in gui.KEYBOARD_KEYS for key in keys):
                raise ValueError("Teclas inválidas. Ejemplo: ctrl+a o enter.")
            gui.hotkey(*keys)
            return {"pressed": keys}
        if action == "type_text":
            text = params.get("text", "")
            if not isinstance(text, str) or not 1 <= len(text) <= 4000:
                raise ValueError("El texto debe tener entre 1 y 4000 caracteres.")

            def check():
                self.access.check()
                gui.failSafeCheck()

            send_unicode(text, check=check)
            return {"typed_characters": len(text)}
        if action == "activate":
            import pygetwindow

            title = params.get("title", "").strip()
            if not title:
                raise ValueError("Indica el título de la ventana.")
            windows = [w for w in pygetwindow.getAllWindows() if title.lower() in w.title.lower()]
            if len(windows) != 1:
                raise ValueError("El título debe identificar exactamente una ventana abierta.")
            if windows[0].isMinimized:
                windows[0].restore()
            windows[0].activate()
            return {"activated": windows[0].title}
        raise ValueError("Acción de escritorio desconocida")

    def screenshot(self):
        self.access.check()
        import pyautogui

        image = pyautogui.screenshot()
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue(), image.size


class DesktopTool(BaseTool):
    tool_id = "desktop_control"

    def __init__(self, driver):
        self.driver = driver

    @property
    def spec(self):
        return ToolSpec(
            name=self.tool_id,
            category="escritorio",
            required_capabilities=["code:execute"],
            description=(
                "Control REAL del ratón y teclado. Primero usa inspect para conocer "
                "pantalla/ventanas; usa desktop_observe para ver objetivos. "
                "Nunca inventes coordenadas. type_text escribe, sin pulsar Enter."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "inspect",
                            "move",
                            "click",
                            "double_click",
                            "scroll",
                            "press",
                            "type_text",
                            "activate",
                        ],
                    },
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"]},
                    "amount": {"type": "integer"},
                    "keys": {"type": "string"},
                    "text": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["action"],
            },
        )

    def execute(self, **params):
        try:
            action = params.pop("action", "inspect")
            result = self.driver.perform(action, **params)
            return ToolResult(
                tool_name=self.tool_id, success=True, content=json.dumps(result, ensure_ascii=False)
            )
        except Exception as exc:
            return ToolResult(tool_name=self.tool_id, success=False, content=str(exc))


class ObserveDesktopTool(BaseTool):
    tool_id = "desktop_observe"

    def __init__(self, driver, describe):
        self.driver, self.describe = driver, describe

    @property
    def spec(self):
        return ToolSpec(
            name=self.tool_id,
            category="escritorio",
            required_capabilities=["file:read"],
            description="Ve una captura real de la pantalla y describe objetivos y coordenadas.",
            parameters={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Qué necesitas localizar o leer"},
                },
                "required": ["question"],
            },
        )

    def execute(self, **params):
        try:
            image, size = self.driver.screenshot()
            description = self.describe(image, size, params.get("question", "Describe la pantalla"))
            return ToolResult(tool_name=self.tool_id, success=True, content=description)
        except Exception as exc:
            return ToolResult(tool_name=self.tool_id, success=False, content=str(exc))
