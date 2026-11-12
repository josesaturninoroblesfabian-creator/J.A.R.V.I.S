"""Bounded, transactional conversation history; no GUI or model dependencies."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class ConversationHistory:
    def __init__(self, path: Path, *, max_messages=20, max_chars=12000):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.max_messages = max_messages
        self.max_chars = max_chars
        self.active_id = "principal"
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
            if "conversation_id" not in columns:
                db.execute(
                    "ALTER TABLE messages ADD COLUMN conversation_id "
                    "TEXT NOT NULL DEFAULT 'principal'"
                )
            db.execute("""CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute(
                "INSERT OR IGNORE INTO conversations(id,title) "
                "VALUES ('principal','Conversación principal')"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id,id)"
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            # Connection.__exit__ commits but does not close SQLite handles.
            connection.close()

    def append_turn(self, user: str, assistant: str):
        # A completed turn is one transaction; a failure leaves no orphan user.
        with self._connect() as db:
            db.executemany(
                "INSERT INTO messages(role, content, conversation_id) VALUES (?, ?, ?)",
                [("user", user, self.active_id), ("assistant", assistant, self.active_id)],
            )
            db.execute(
                """UPDATE conversations SET updated_at=CURRENT_TIMESTAMP,
                title=CASE WHEN title='Nueva conversación' THEN ? ELSE title END WHERE id=?""",
                (user[:55], self.active_id),
            )
            db.execute(
                """DELETE FROM messages WHERE conversation_id=? AND id NOT IN
                (SELECT id FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 200)""",
                (self.active_id, self.active_id),
            )

    def recent(self):
        with self._connect() as db:
            rows = db.execute(
                "SELECT role, content FROM messages WHERE conversation_id=? "
                "ORDER BY id DESC LIMIT ?",
                (self.active_id, self.max_messages),
            ).fetchall()
        # Retain complete turns, starting with a user message. Stop before
        # exceeding the character budget instead of cutting a message in half.
        selected, size = [], 0
        for i in range(0, len(rows) - 1, 2):
            assistant, user = rows[i : i + 2]
            turn_size = len(assistant[1]) + len(user[1])
            if size + turn_size > self.max_chars:
                break
            selected.extend((assistant, user))
            size += turn_size
        return list(reversed(selected))

    def clear(self):
        with self._connect() as db:
            db.execute("DELETE FROM messages WHERE conversation_id=?", (self.active_id,))

    def conversations(self):
        with self._connect() as db:
            return [
                {"id": row[0], "title": row[1]}
                for row in db.execute(
                    "SELECT id,title FROM conversations ORDER BY updated_at DESC,rowid DESC"
                )
            ]

    def create(self):
        identifier = uuid.uuid4().hex
        with self._connect() as db:
            db.execute(
                "INSERT INTO conversations(id,title) VALUES (?, 'Nueva conversación')",
                (identifier,),
            )
        self.active_id = identifier
        return identifier

    def activate(self, identifier):
        with self._connect() as db:
            if (
                db.execute("SELECT 1 FROM conversations WHERE id=?", (identifier,)).fetchone()
                is None
            ):
                raise ValueError("La conversación no existe")
        self.active_id = identifier
