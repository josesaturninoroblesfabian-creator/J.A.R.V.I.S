"""Explicit native-app model selection; never changes the user's SDK config."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from app_paths import profile_path

PROFILE_PATH = profile_path()


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    engine: str
    model: str
    api_key_env: str = ""
    max_tokens: int | None = None
    vision: bool = False
    local_vision_model: str = ""

    def validate_credentials(self) -> None:
        from credential_store import get_credential

        if self.api_key_env and not get_credential(self.api_key_env):
            raise ValueError(
                f"El perfil {self.name} necesita {self.api_key_env}. "
                "Configura la clave en tu equipo o selecciona un perfil local."
            )


@dataclass(frozen=True)
class NativeSettings:
    profile: Profile
    profiles: dict[str, Profile]
    history_messages: int = 20
    history_chars: int = 12000
    warmup: bool = False
    voice_mode: str = "light"
    allow_local_vision: bool = False


def load_settings(path: Path = PROFILE_PATH, profile_name: str | None = None):
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    profiles = {}
    for name, values in data.get("profiles", {}).items():
        profile = Profile(name=name, **values)
        if profile.max_tokens is not None and (
            type(profile.max_tokens) is not int or profile.max_tokens < 1
        ):
            raise ValueError(f"max_tokens inválido para {name}")
        profiles[name] = profile
    active = profile_name or os.environ.get("JARVIS_PROFILE") or data.get("active")
    if active not in profiles:
        raise ValueError(f"Perfil desconocido: {active}. Opciones: {', '.join(profiles)}")
    for key in ("history_messages", "history_chars"):
        value = data.get(key, 20 if key == "history_messages" else 12000)
        if type(value) is not int or value < 2:
            raise ValueError(f"{key} debe ser un entero mayor o igual a 2")
    return NativeSettings(
        profile=profiles[active],
        profiles=profiles,
        history_messages=data.get("history_messages", 20),
        history_chars=data.get("history_chars", 12000),
        warmup=data.get("warmup", False),
        voice_mode=data.get("voice_mode", "light"),
        allow_local_vision=data.get("allow_local_vision", False),
    )


def profile_config(config, profile: Profile):
    result = copy.deepcopy(config)
    if profile.engine:
        result.engine.default = profile.engine
        result.intelligence.preferred_engine = profile.engine
    if profile.model:
        result.intelligence.default_model = profile.model
    if profile.max_tokens is not None:
        result.intelligence.max_tokens = profile.max_tokens
    return result
