"""Per-user Windows-protected credentials. No plaintext keys in project settings."""

from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes
from pathlib import Path

from app_paths import data_dir

DEFAULT_DIR = data_dir() / "credentials"


def _protect(data: bytes, *, decrypt=False):
    if os.name != "nt":
        raise RuntimeError("En este sistema configura la clave mediante una variable de entorno.")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_byte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("Windows no pudo abrir o proteger la credencial de este usuario.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


class CredentialStore:
    def __init__(self, directory=DEFAULT_DIR):
        self.directory = Path(directory)

    def _path(self, name):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", name):
            raise ValueError("Nombre de credencial inválido")
        return self.directory / f"{name}.dpapi"

    def save(self, name, value):
        value = value.strip()
        if not value or len(value) > 4096:
            raise ValueError("La clave está vacía o no tiene un tamaño válido.")
        encrypted = _protect(value.encode())
        path = self._path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        temporary.replace(path)

    def load(self, name):
        path = self._path(name)
        if not path.exists():
            return ""
        return _protect(path.read_bytes(), decrypt=True).decode()

    def available(self, name):
        return bool(os.environ.get(name, "").strip() or self._path(name).exists())


def get_credential(name):
    return os.environ.get(name, "").strip() or CredentialStore().load(name)


def credential_error(exc):
    """Never put SDK exception bodies or credential values into user-facing messages."""
    from provider_errors import ProviderBusy

    if isinstance(exc, ProviderBusy):
        return str(exc)
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return "Groq rechazó la clave o el acceso al modelo. Actualízala en Cerebro."
    if status == 429:
        return "Groq alcanzó su cuota temporal. Espera o selecciona un modelo local."
    if status == 400:
        return "Groq rechazó el formato de la petición o sus límites de contexto."
    return "No se pudo conectar con Groq. Revisa la conexión y vuelve a probar."
