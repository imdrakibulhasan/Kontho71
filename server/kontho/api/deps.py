"""Shared API dependencies: auth, error mapping, upload helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi import Header, HTTPException, UploadFile
from fastapi.responses import Response

from .. import audio as A
from .. import db, storage
from ..config import get_settings
from ..engines import EngineUnavailable


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_api_key(name: str) -> tuple[str, dict]:
    raw = "kt_" + secrets.token_urlsafe(32)
    row = {"id": db.new_id("key_"), "name": name, "prefix": raw[:8], "key_hash": hash_key(raw),
           "created_at": db.now(), "last_used_at": None}
    db.insert("api_keys", row)
    return raw, row


def require_api_key(xi_api_key: str | None = Header(default=None),
                    authorization: str | None = Header(default=None)) -> None:
    s = get_settings()
    if not s.auth_enabled:
        return
    key = xi_api_key or (authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None)
    if not key:
        raise HTTPException(401, {"status": "missing_api_key", "message": "Send your key in the xi-api-key header"})
    if s.admin_key and secrets.compare_digest(key, s.admin_key):
        return
    rows = db.query("SELECT id FROM api_keys WHERE key_hash = ?", (hash_key(key),))
    if not rows:
        raise HTTPException(401, {"status": "invalid_api_key", "message": "Invalid API key"})
    db.update("api_keys", rows[0]["id"], {"last_used_at": db.now()})


@contextmanager
def errors() -> Iterator[None]:
    """Translate service exceptions into HTTP errors (ElevenLabs-style ``detail`` objects)."""
    try:
        yield
    except HTTPException:
        raise
    except KeyError as exc:
        raise HTTPException(404, {"status": "not_found", "message": str(exc).strip("'\"")}) from exc
    except EngineUnavailable as exc:
        raise HTTPException(503, {"status": "engine_unavailable", "message": str(exc)}) from exc
    except (ValueError, A.AudioError) as exc:
        raise HTTPException(422, {"status": "invalid_request", "message": str(exc)}) from exc


def save_uploads(files: list[UploadFile], folder: str) -> list[Path]:
    d = storage.dir_for("uploads", folder)
    out = []
    for i, f in enumerate(files):
        with errors():
            out.append(storage.save_upload(f, d / f"{i}{storage.safe_suffix(f.filename, '.wav')}"))
    return out


def parse_json_field(value: str | None, field: str) -> dict:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, {"status": "invalid_request", "message": f"{field} must be JSON"}) from exc
    if not isinstance(data, dict):
        raise HTTPException(422, {"status": "invalid_request", "message": f"{field} must be a JSON object"})
    return data


def audio_response(audio, sr: int, output_format: str | None, history_id: str | None = None,
                   filename: str = "audio") -> Response:
    with errors():
        fmt = A.parse_output_format(output_format)
        data = A.encode(audio, sr, fmt)
    headers = {"Content-Disposition": f'inline; filename="{filename}.{fmt.extension}"'}
    if history_id:
        headers["history-item-id"] = history_id
    return Response(data, media_type=fmt.content_type, headers=headers)
