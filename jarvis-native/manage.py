"""Text entry point for diagnostics and native profiles without loading Qt."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os

from profiles import load_settings


def main():
    parser = argparse.ArgumentParser(description="Jarvis: perfiles, diagnóstico y chat")
    parser.add_argument("command", choices=["profiles", "check", "chat"])
    parser.add_argument("--profile")
    args = parser.parse_args()
    settings = load_settings(profile_name=args.profile)
    if args.command == "profiles":
        for name, profile in settings.profiles.items():
            active = "*" if name == settings.profile.name else " "
            print(f"{active} {name}: {profile.label}")
        return
    if args.command == "check":
        profile = settings.profile
        print(
            json.dumps(
                {
                    "profile": profile.name,
                    "engine": profile.engine,
                    "model": profile.model,
                    "credential_present": bool(os.environ.get(profile.api_key_env, "").strip())
                    if profile.api_key_env
                    else None,
                    "packages": {
                        name: importlib.util.find_spec(name) is not None
                        for name in ["openjarvis", "PySide6", "sounddevice", "faster_whisper"]
                    },
                    "note": "Diagnóstico sin conexión: no confirma disponibilidad de la API.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    from brain import JarvisBrain

    def confirm(prompt):
        return input(f"{prompt}\n¿Autorizar? [s/N] ").strip().lower() == "s"

    brain = JarvisBrain(settings=settings, confirm_callback=confirm)
    try:
        # Text mode intentionally avoids loading microphones and speech models.
        brain._init_voice = lambda: None
        brain.init()
        print(f"Jarvis · {brain.profile.label} · /salir para terminar")
        while True:
            try:
                query = input("Tú: ").strip()
            except EOFError:
                break
            if query == "/salir":
                break
            print(f"Jarvis: {brain.ask(query)}")
    finally:
        brain.close()


if __name__ == "__main__":
    main()
