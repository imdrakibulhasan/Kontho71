"""File storage under ``$KONTHO_DATA_DIR/files``."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import UploadFile

from .config import get_settings


def path_for(*parts: str) -> Path:
    p = get_settings().files_dir.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def dir_for(*parts: str) -> Path:
    p = get_settings().files_dir.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_suffix(name: str | None, default: str = ".bin") -> str:
    suffix = Path(name or "").suffix.lower()
    return suffix if suffix and len(suffix) <= 6 and suffix[1:].isalnum() else default


def save_upload(upload: UploadFile, dest: Path) -> Path:
    """Copy an upload to ``dest`` (sync; endpoints run in the threadpool)."""
    limit = get_settings().max_upload_mb * 1024 * 1024
    size = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    upload.file.seek(0)
    with dest.open("wb") as f:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                dest.unlink(missing_ok=True)
                raise ValueError(f"File too large (limit {get_settings().max_upload_mb} MB)")
            f.write(chunk)
    return dest


def remove_tree(path: Path) -> None:
    root = get_settings().files_dir.resolve()
    path = path.resolve()
    if root in path.parents and path.exists():
        shutil.rmtree(path) if path.is_dir() else path.unlink()
