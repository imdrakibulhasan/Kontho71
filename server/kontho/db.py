"""Tiny SQLite persistence layer (stdlib only)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from .config import get_settings

_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS voices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT NOT NULL,              -- premade | cloned | designed
    language TEXT DEFAULT '',
    labels TEXT DEFAULT '{}',            -- JSON: gender, age, accent, use_case...
    ref_audio TEXT,                      -- path of the reference clip (cloned / designed voices)
    ref_text TEXT,                       -- exact words spoken in the reference clip
    instruct TEXT,                       -- voice-design prompt (premade / designed voices)
    preview TEXT,                        -- path of a preview clip
    settings TEXT DEFAULT '{}',          -- JSON: default voice settings
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,                  -- tts | sts | sfx | isolation | stt | design
    voice_id TEXT,
    voice_name TEXT,
    text TEXT,
    settings TEXT DEFAULT '{}',
    audio TEXT,
    content_type TEXT,
    characters INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT DEFAULT '',
    status TEXT NOT NULL,                -- queued | running | done | failed
    progress REAL DEFAULT 0,
    message TEXT DEFAULT '',
    input TEXT DEFAULT '{}',
    result TEXT DEFAULT '{}',
    error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    last_used_at REAL
);
CREATE TABLE IF NOT EXISTS voice_emotions (
    id TEXT PRIMARY KEY,
    voice_id TEXT NOT NULL,
    emotion TEXT NOT NULL,               -- canonical emotion (see emotions.py)
    ref_audio TEXT NOT NULL,             -- reference clip spoken with that emotion
    ref_text TEXT,                       -- exact words of the clip
    created_at REAL NOT NULL,
    UNIQUE (voice_id, emotion)
);
CREATE TABLE IF NOT EXISTS pronunciation (
    id TEXT PRIMARY KEY,
    term TEXT NOT NULL,
    replacement TEXT NOT NULL,
    language TEXT DEFAULT '',
    created_at REAL NOT NULL
);
"""

JSON_COLUMNS = {"labels", "settings", "input", "result"}


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:20]


def now() -> float:
    return time.time()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_settings().db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        with _lock:
            yield conn
            conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for k in JSON_COLUMNS & out.keys():
        try:
            out[k] = json.loads(out[k]) if out[k] else {}
        except (TypeError, json.JSONDecodeError):
            out[k] = {}
    return out


def _encode(values: dict[str, Any]) -> dict[str, Any]:
    return {k: (json.dumps(v, ensure_ascii=False) if k in JSON_COLUMNS else v) for k, v in values.items()}


def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    vals = _encode(values)
    cols = ", ".join(vals)
    qs = ", ".join("?" for _ in vals)
    with connect() as c:
        c.execute(f"INSERT INTO {table} ({cols}) VALUES ({qs})", list(vals.values()))
    return values


def update(table: str, id_: str, values: dict[str, Any]) -> None:
    vals = _encode(values)
    sets = ", ".join(f"{k} = ?" for k in vals)
    with connect() as c:
        c.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*vals.values(), id_])


def get(table: str, id_: str) -> dict[str, Any] | None:
    with connect() as c:
        return _decode(c.execute(f"SELECT * FROM {table} WHERE id = ?", (id_,)).fetchone())


def delete(table: str, id_: str) -> bool:
    with connect() as c:
        return c.execute(f"DELETE FROM {table} WHERE id = ?", (id_,)).rowcount > 0


def query(sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
    with connect() as c:
        return [_decode(r) for r in c.execute(sql, params).fetchall()]  # type: ignore[misc]
