"""Shared camera opening and warm-up for presence and explicit vision requests."""

import threading


def open_camera(index=0, preference="auto", cancelled=None):
    import cv2

    cancelled = cancelled or threading.Event()
    choices = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "default": cv2.CAP_ANY}
    names = [preference] if preference in choices else ["dshow", "msmf", "default"]
    for name in names:
        if cancelled.is_set():
            raise RuntimeError("Apertura de cámara cancelada.")
        capture = cv2.VideoCapture(index, choices[name])
        try:
            if capture.isOpened():
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                capture.set(cv2.CAP_PROP_FPS, 5)
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                for _ in range(8):
                    if cancelled.is_set():
                        break
                    ok, frame = capture.read()
                    if ok and frame is not None:
                        return capture, frame, name
                    cancelled.wait(0.08)
        except Exception:
            capture.release()
            raise
        capture.release()
    raise RuntimeError(
        f"La cámara {index} no entregó imagen. Prueba otra cámara o método en Compañero; "
        "cierra otras apps que la estén usando y revisa el permiso de cámara de Windows."
    )
