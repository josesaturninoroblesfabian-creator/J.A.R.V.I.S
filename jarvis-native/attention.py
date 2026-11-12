"""Small local sensors. Never capture screen images or send foreground titles to an API."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QThread, Signal

from companion import Observation


def foreground_observation():
    try:
        import psutil

        user = ctypes.WinDLL("user32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        user.GetForegroundWindow.restype = wintypes.HWND
        user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetTickCount64.restype = ctypes.c_ulonglong

        class LastInput(ctypes.Structure):
            _fields_ = [("size", wintypes.UINT), ("tick", wintypes.DWORD)]

        last = LastInput(ctypes.sizeof(LastInput), 0)
        if not user.GetLastInputInfo(ctypes.byref(last)):
            return Observation(available=False)
        idle = ((kernel.GetTickCount64() - last.tick) & 0xFFFFFFFF) / 1000
        hwnd = user.GetForegroundWindow()
        if not hwnd:
            return Observation(idle_seconds=idle, available=False, locked=True)
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = psutil.Process(pid.value).name()
        if process.lower() in {"lockapp.exe", "logonui.exe"}:
            return Observation(idle_seconds=idle, available=False, locked=True)
        title = ctypes.create_unicode_buffer(1024)
        user.GetWindowTextW(hwnd, title, len(title))
        return Observation(app=process, title=title.value, idle_seconds=idle)
    except (OSError, AttributeError, ImportError):
        return Observation(available=False)
    except Exception:
        # A foreground process can close between GetForegroundWindow and name().
        return Observation(available=False)


class PresenceWorker(QThread):
    sample = Signal(object)
    error = Signal(str)
    opened = Signal(str)

    def __init__(self, parent=None, *, index=0, backend="auto"):
        import threading

        super().__init__(parent)
        self.cancelled = threading.Event()
        self.index, self.backend = index, backend
        self._frame = None
        self._frame_lock = threading.Lock()

    def snapshot(self):
        import cv2

        with self._frame_lock:
            frame = self._frame.copy() if self._frame is not None else None
        if frame is None or self.cancelled.is_set():
            raise RuntimeError("La cámara todavía no tiene una imagen disponible.")
        ok, data = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("No se pudo preparar la imagen de la cámara.")
        return data.tobytes()

    def stop(self):
        self.cancelled.set()

    def run(self):
        import cv2

        camera = None
        try:
            detector = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            if detector.empty():
                raise RuntimeError("Detector de presencia no disponible.")
            from camera_device import open_camera

            cv2.setNumThreads(1)
            camera, initial, method = open_camera(self.index, self.backend, self.cancelled)
            self.opened.emit(f"Cámara {self.index} activa · método {method}")
            with self._frame_lock:
                self._frame = initial
            failures = 0
            while not self.cancelled.is_set():
                ok, frame = camera.read()
                if self.cancelled.is_set():
                    break
                if not ok:
                    failures += 1
                    if failures >= 3:
                        raise RuntimeError("La cámara dejó de responder. Puedes seguir sin ella.")
                else:
                    failures = 0
                    frame = cv2.resize(frame, (320, 240))
                    with self._frame_lock:
                        self._frame = frame
                    faces = detector.detectMultiScale(
                        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                        scaleFactor=1.15,
                        minNeighbors=5,
                        minSize=(40, 40),
                    )
                    point = None
                    if len(faces):
                        x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
                        point = (1 - 2 * (x + w / 2) / 320, 2 * (y + h / 2) / 240 - 1)
                    self.sample.emit({"present": bool(len(faces)), "point": point})
                # No video is saved, displayed or sent; at most one detection a second.
                self.cancelled.wait(1.5)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            with self._frame_lock:
                self._frame = None
            if camera is not None:
                camera.release()
