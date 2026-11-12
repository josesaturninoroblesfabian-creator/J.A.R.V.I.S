"""Resident-app lifecycle: recover local Ollama and prevent duplicate desktops."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def local_engine_url(url: str) -> str:
    if not url:
        return "http://127.0.0.1:11434"
    parts = urlsplit(url)
    if parts.hostname == "localhost":
        return urlunsplit(parts._replace(netloc=f"127.0.0.1:{parts.port or 11434}"))
    return url


def ensure_ollama(url: str, *, timeout=20, on_status=None):
    url = local_engine_url(url).rstrip("/")
    with httpx.Client(timeout=1.5, trust_env=False) as client:

        def available():
            try:
                response = client.get(f"{url}/api/tags")
                return response.status_code == 200 and isinstance(
                    response.json().get("models"), list
                )
            except (httpx.HTTPError, ValueError):
                return False

        if available():
            return
        parts = urlsplit(url)
        if parts.hostname not in {"localhost", "127.0.0.1", "::1"} or parts.port != 11434:
            raise RuntimeError("No se puede conectar con el servidor Ollama configurado.")
        executable = shutil.which("ollama")
        if not executable:
            candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Ollama/ollama.exe"
            if candidate.is_file():
                executable = str(candidate)
        if not executable:
            raise RuntimeError("Ollama no está instalado o no se encuentra en este equipo.")
        if on_status:
            on_status("Iniciando Ollama…")
        subprocess.Popen(
            [executable, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if available():
                return
            time.sleep(0.25)
        raise RuntimeError("Ollama no respondió al arrancar. Usa «Reconectar» para reintentarlo.")


class SingleInstance(QObject):
    show_requested = Signal()

    def __init__(self, directory: Path):
        super().__init__()
        directory.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(directory / "desktop.lock"))
        self._lock.setStaleLockTime(0)
        suffix = hashlib.sha256(str(directory.resolve()).lower().encode()).hexdigest()[:20]
        self._name = f"JarvisPersonal-{suffix}"
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._accept)
        self._connections = []

    def acquire(self):
        if not self._lock.tryLock(0):
            client = QLocalSocket()
            client.connectToServer(self._name)
            if client.waitForConnected(1000):
                client.write(b"show")
                client.waitForBytesWritten(1000)
                client.disconnectFromServer()
            return False
        QLocalServer.removeServer(self._name)
        if not self._server.listen(self._name):
            self._lock.unlock()
            raise RuntimeError("No se pudo crear el canal de la aplicación Jarvis.")
        return True

    def _accept(self):
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._connections.append(socket)
            socket.readyRead.connect(lambda socket=socket: self._read(socket))
            socket.disconnected.connect(lambda socket=socket: self._remove(socket))
            if socket.bytesAvailable():
                self._read(socket)

    def _read(self, socket):
        if bytes(socket.readAll()) == b"show":
            self.show_requested.emit()

    def _remove(self, socket):
        if socket in self._connections:
            self._connections.remove(socket)
        socket.deleteLater()

    def close(self):
        for socket in self._connections[:]:
            socket.abort()
        self._server.close()
        self._lock.unlock()
