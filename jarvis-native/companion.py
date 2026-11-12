"""Local companion policy and focus clock, independent of Qt and model/tool access."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


def plain(text):
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(ch) != "Mn"
    )


@dataclass
class CompanionSettings:
    enabled: bool = True
    spoken: bool = True
    avatar: bool = True
    observe_apps: bool = True
    followup: bool = True
    style: str = "cercano"
    work_minutes: int = 25
    break_minutes: int = 5
    checkin_minutes: int = 30
    distraction_seconds: int = 45
    cooldown_seconds: int = 180
    quiet_start: int = 22
    quiet_end: int = 8
    distractions: str = "youtube, tiktok, instagram, facebook, netflix, twitch, shorts"
    allowed: str = ""

    def validate(self):
        for key, lower, upper in [
            ("work_minutes", 1, 120),
            ("break_minutes", 1, 30),
            ("checkin_minutes", 5, 180),
            ("distraction_seconds", 15, 600),
            ("cooldown_seconds", 60, 1800),
            ("quiet_start", 0, 23),
            ("quiet_end", 0, 23),
        ]:
            value = getattr(self, key)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"Valor inválido para {key}")
        if self.style not in {"cercano", "suave", "directo"}:
            raise ValueError("Estilo de acompañamiento inválido")
        for field in ["enabled", "spoken", "avatar", "observe_apps", "followup"]:
            if type(getattr(self, field)) is not bool:
                raise ValueError(f"Valor inválido para {field}")
        if len(self.distractions) > 2000 or len(self.allowed) > 2000:
            raise ValueError("La lista de aplicaciones es demasiado larga")
        return self

    def quiet(self, hour):
        if self.quiet_start == self.quiet_end:
            return False
        if self.quiet_start < self.quiet_end:
            return self.quiet_start <= hour < self.quiet_end
        return hour >= self.quiet_start or hour < self.quiet_end


@dataclass(frozen=True)
class Observation:
    app: str = ""
    title: str = ""
    idle_seconds: float = 0
    available: bool = True
    locked: bool = False
    present: bool | None = None


@dataclass(frozen=True)
class Cue:
    kind: str
    text: str


class CompanionStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY, data TEXT);
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY, goal TEXT, started TEXT, ended TEXT,
                    duration_seconds INTEGER DEFAULT 0, nudges INTEGER DEFAULT 0, status TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, created TEXT, session_id INTEGER, kind TEXT, text TEXT
                );
            """)
            db.execute(
                "UPDATE sessions SET status='interrumpida',ended=? WHERE ended IS NULL",
                (self.timestamp(),),
            )

    def connect(self):
        # closing() matters on Windows: connection context managers only commit.
        return _Connection(self.path)

    @staticmethod
    def timestamp():
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def settings(self):
        try:
            with self.connect() as db:
                row = db.execute("SELECT data FROM preferences WHERE id=1").fetchone()
            data = json.loads(row[0]) if row else {}
            return CompanionSettings(**data).validate()
        except (TypeError, ValueError):
            return CompanionSettings()

    def save_settings(self, settings):
        settings.validate()
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO preferences VALUES (1,?)", (json.dumps(asdict(settings)),)
            )

    def start(self, goal):
        with self.connect() as db:
            return db.execute(
                "INSERT INTO sessions(goal,started,status) VALUES (?,?,'en curso')",
                (goal, self.timestamp()),
            ).lastrowid

    def finish(self, session_id, seconds, nudges, status):
        with self.connect() as db:
            db.execute(
                "UPDATE sessions SET ended=?,duration_seconds=?,nudges=?,status=? WHERE id=?",
                (self.timestamp(), int(seconds), nudges, status, session_id),
            )

    def event(self, cue, session_id=None):
        with self.connect() as db:
            db.execute(
                "INSERT INTO events(created,session_id,kind,text) VALUES (?,?,?,?)",
                (self.timestamp(), session_id, cue.kind, cue.text),
            )
            db.execute(
                "DELETE FROM events WHERE id NOT IN (SELECT id FROM events "
                "ORDER BY id DESC LIMIT 200)"
            )

    def recent(self):
        with self.connect() as db:
            return db.execute(
                "SELECT created,kind,text FROM events ORDER BY id DESC LIMIT 20"
            ).fetchall()

    def summary(self):
        today = datetime.now().astimezone().date().isoformat()
        with self.connect() as db:
            seconds, sessions = db.execute(
                "SELECT COALESCE(SUM(duration_seconds),0),COUNT(*) FROM sessions "
                "WHERE status='completada' AND substr(started,1,10)=?",
                (today,),
            ).fetchone()
        return {"minutes": int(seconds // 60), "sessions": sessions}


class _Connection:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=5)

    def __enter__(self):
        return self.db

    def __exit__(self, *exc):
        try:
            self.db.__exit__(*exc)
        finally:
            self.db.close()


class FocusCompanion:
    def __init__(self, store, *, clock=time.monotonic):
        self.store, self.clock = store, clock
        self.settings = store.settings()
        self.phase, self.goal, self.session_id = "ready", "", None
        self.elapsed = self.work_seconds = self.nudges = 0
        self.duration = 0
        self.paused = False
        self.last_tick = self.clock()
        self.last_cue = self.last_tick
        self.last_nudge = float("-inf")
        self.snoozed_until = 0
        self.distracted_since = self.away_since = None
        self.pending = None

    def configure(self, settings):
        settings.validate()
        self.store.save_settings(settings)
        self.settings = settings
        self.distracted_since = self.away_since = None
        if not settings.enabled:
            self.pending = None

    def start(self, goal, minutes=None, *, now=None):
        goal = goal.strip()
        minutes = self.settings.work_minutes if minutes is None else minutes
        if not goal or len(goal) > 500 or type(minutes) is not int or not 1 <= minutes <= 120:
            raise ValueError("Escribe una meta breve y elige entre 1 y 120 minutos.")
        if self.phase == "focus":
            self.finish("interrumpida")
        self.phase, self.goal = "focus", goal
        self.session_id = self.store.start(goal)
        self.elapsed = self.work_seconds = self.nudges = 0
        self.duration = minutes * 60
        self.paused, self.pending = False, None
        self.last_tick = self.clock() if now is None else now
        self.last_cue = self.last_tick
        self.last_nudge = float("-inf")
        self.distracted_since = self.away_since = None
        return Cue(
            "start",
            f"Vamos con {goal}. Un paso a la vez durante {minutes} minutos. "
            "Estoy aquí si necesitas volver al foco.",
        )

    def toggle_pause(self, *, now=None):
        if self.phase not in {"focus", "break"}:
            return Cue("info", "Primero inicia una sesión de enfoque.")
        self.paused = not self.paused
        self.last_tick = self.clock() if now is None else now
        self.distracted_since = self.away_since = None
        self.pending = None
        return Cue(
            "pause",
            "Sesión en pausa. Tómate el tiempo que necesites."
            if self.paused
            else "Seguimos. Elige el siguiente paso más pequeño.",
        )

    def finish(self, status="terminada"):
        if self.session_id is not None:
            self.store.finish(self.session_id, self.work_seconds, self.nudges, status)
        self.session_id, self.phase, self.pending = None, "ready", None
        self.paused = False
        return Cue(
            "finish", "Sesión cerrada. Lo que avanzaste cuenta. Puedes empezar otra cuando quieras."
        )

    def snooze(self, minutes=10, *, now=None):
        self.snoozed_until = (self.clock() if now is None else now) + minutes * 60
        self.pending = None
        self.distracted_since = self.away_since = None

    def classify(self, observation):
        haystack = plain(observation.app + " " + observation.title)
        # Only explicit user exceptions override leisure matches; a productive
        # app name alone is not evidence that its current page is productive.
        for word in self.settings.allowed.split(","):
            if word.strip() and plain(word.strip()) in haystack:
                return "allowed"
        for word in self.settings.distractions.split(","):
            if word.strip() and plain(word.strip()) in haystack:
                return "distraction"
        return "unknown"

    def tick(self, observation, *, now=None, hour=None, can_interrupt=True):
        now = self.clock() if now is None else now
        hour = datetime.now().astimezone().hour if hour is None else hour
        delta = max(0, now - self.last_tick)
        self.last_tick = now
        if observation.locked or delta > 60:
            # Sleep/locked desktop is not work or distraction evidence.
            self.distracted_since = self.away_since = None
            return None
        if self.phase in {"focus", "break"} and not self.paused:
            self.elapsed += delta
            if self.phase == "focus":
                self.work_seconds = min(self.elapsed, self.duration)
            if self.elapsed >= self.duration:
                if self.phase == "focus":
                    self.store.finish(self.session_id, self.work_seconds, self.nudges, "completada")
                    self.session_id = None
                    self.phase, self.elapsed = "break", 0
                    self.duration = self.settings.break_minutes * 60
                    self.pending = Cue(
                        "break",
                        f"Completaste tu bloque de {self.goal}. "
                        f"Descansa {self.settings.break_minutes} minutos: "
                        "levántate un momento y deja descansar la vista.",
                    )
                else:
                    self.phase, self.elapsed = "ready", 0
                    self.pending = Cue(
                        "return",
                        "Terminó la pausa. ¿Iniciamos otro bloque o prefieres ajustar la meta?",
                    )
        if self.paused or not self.settings.enabled:
            return None
        if self.settings.quiet(hour) or now < self.snoozed_until:
            self.distracted_since = self.away_since = None
            return None
        if self.phase == "focus" and self.settings.observe_apps and observation.available:
            away = observation.present is False or observation.idle_seconds > 300
            if away:
                self.distracted_since = None
                if self.away_since is None:
                    self.away_since = now
                if now - self.away_since >= 60 and not self.pending:
                    self.pending = Cue(
                        "away",
                        "Llevas un rato sin actividad. Si saliste, "
                        "puedes pausar la sesión; si estás leyendo, sigue con calma.",
                    )
            else:
                self.away_since = None
                if self.pending and self.pending.kind == "away":
                    self.pending = None
                if self.classify(observation) == "distraction":
                    if self.distracted_since is None:
                        self.distracted_since = now
                    if (
                        now - self.distracted_since >= self.settings.distraction_seconds
                        and not self.pending
                    ):
                        self.pending = Cue(
                            "distraction",
                            f"Parece que abriste contenido de ocio. "
                            f"¿Volvemos a {self.goal} con un paso pequeño? "
                            "Si es parte de tu tarea, puedes añadir una excepción.",
                        )
                else:
                    self.distracted_since = None
                    if self.pending and self.pending.kind == "distraction":
                        self.pending = None
        else:
            self.distracted_since = self.away_since = None
        if not can_interrupt:
            return None
        if self.pending:
            transition = self.pending.kind in {"break", "return"}
            if transition or now - self.last_nudge >= self.settings.cooldown_seconds:
                cue, self.pending = self.pending, None
                self.last_cue = now
                self.last_nudge = now
                self.distracted_since = self.away_since = None
                if cue.kind == "distraction":
                    self.nudges += 1
                return cue
        if (
            self.phase in {"ready", "focus"}
            and observation.available
            and observation.present is not False
            and 3 <= observation.idle_seconds < 300
            and now - self.last_cue >= self.settings.checkin_minutes * 60
        ):
            self.last_cue = now
            self.last_nudge = now
            return Cue(
                "checkin",
                "¿Cómo vas con tu siguiente paso? Si te atascaste, "
                "dime qué intentas hacer y lo dividimos en algo pequeño."
                if self.phase == "focus"
                else "Estoy por aquí. ¿Conversamos o elegimos una meta pequeña para hoy?",
            )
        return None

    def snapshot(self):
        return {
            "phase": self.phase,
            "goal": self.goal,
            "paused": self.paused,
            "remaining": max(0, int(self.duration - self.elapsed)),
            "work_seconds": int(self.work_seconds),
            "nudges": self.nudges,
            "enabled": self.settings.enabled,
        }

    def context(self):
        if not self.settings.enabled:
            return ""
        text = (
            "Acompañas como un amigo respetuoso y un coach práctico. Escucha antes de aconsejar; "
            "ofrece un paso pequeño, evita sermones, culpa y promesas de vigilancia. "
            "No afirmes saber lo que siente o si presta atención. "
        )
        if self.phase == "focus":
            text += f"Meta de enfoque actual del usuario: {self.goal}. "
            text += "La sesión está pausada. " if self.paused else "La sesión está en curso. "
        return text


def companion_command(text):
    normalized = plain(text).strip(" .!?¿¡")
    normalized = re.sub(r"^(?:jarvis|por favor)[, ]+", "", normalized)
    # Offline recognizers spell out numbers; preserve voice focus commands.
    small = dict(
        zip(
            "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece "
            "catorce quince dieciseis diecisiete dieciocho diecinueve veinte veintiuno "
            "veintidos veintitres veinticuatro veinticinco veintiseis veintisiete "
            "veintiocho veintinueve".split(),
            range(30),
        )
    )
    small["un"] = small["una"] = 1
    tens = {
        "treinta": 30,
        "cuarenta": 40,
        "cincuenta": 50,
        "sesenta": 60,
        "setenta": 70,
        "ochenta": 80,
        "noventa": 90,
        "cien": 100,
    }

    def number(match):
        value = match[1]
        amount = small.get(value, tens.get(value))
        if amount is None and " y " in value:
            first, last = value.split(" y ", 1)
            if first in tens and last in small:
                amount = tens[first] + small[last]
        return f"{amount} minutos" if amount is not None else match[0]

    normalized = re.sub(r"\b(\w+(?: y \w+)?) minutos?\b", number, normalized)
    if normalized in {"me ves", "puedes verme", "esta encendida la camara"}:
        return ("camera_status", {})
    if re.fullmatch(
        r"(?:enciende|prende|activa|abre|inicia) (?:la |mi )?(?:camara|webcam)", normalized
    ):
        return ("camera_on", {})
    if re.fullmatch(r"(?:apaga|desactiva|cierra) (?:la |mi )?(?:camara|webcam)", normalized):
        return ("camera_off", {})
    if re.fullmatch(r"(?:pausa|pausar) (?:el |la )?(?:enfoque|sesion|coach)", normalized):
        return ("pause", {})
    if re.fullmatch(
        r"(?:reanuda|reanudar|continua) (?:el |la )?(?:enfoque|sesion|coach)", normalized
    ):
        return ("resume", {})
    if re.fullmatch(
        r"(?:termina|terminar|cierra|finaliza) (?:el |la )?(?:enfoque|sesion)", normalized
    ):
        return ("finish", {})
    if re.fullmatch(
        r"(?:no me interrumpas|silencio|silencia al coach)(?: por)?(?: 10 minutos)?", normalized
    ):
        return ("snooze", {})
    if normalized in {"me distraje", "necesito apoyo", "dame animo", "ayudame a volver al foco"}:
        return ("support", {})
    match = re.fullmatch(
        r"(?:inicia|iniciar|empieza|comienza|activa) (?:un |una |el |la )?"
        r"(?:enfoque|sesion de enfoque|modo enfoque)(?: de| por| durante)?(?: (\d{1,3}) minutos)?"
        r"(?: (?:para|en) (.{1,500}))?",
        normalized,
    )
    if match:
        return (
            "start",
            {
                "minutes": int(match.group(1)) if match.group(1) else None,
                "goal": match.group(2) or "avanzar en mi tarea",
            },
        )
    return None
