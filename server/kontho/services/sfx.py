"""Sound effects generation and voice isolation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from .. import audio as A
from .. import storage
from ..engines import get_engine


def generate(text: str, duration: float | None = None, prompt_influence: float = 0.3,
             seed: int | None = None) -> tuple[np.ndarray, int]:
    if not text.strip():
        raise ValueError("text is empty")
    duration = float(duration or 5.0)
    if not 0.5 <= duration <= 30.0:
        raise ValueError("duration_seconds must be between 0.5 and 30")
    audio, sr = get_engine("sfx").generate(text, duration, prompt_influence, seed)
    return A.peak_normalize(audio, 0.9), sr


def isolate(path: Path) -> tuple[np.ndarray, np.ndarray, int]:
    """Separate voice from background. Results are cached by file content, so asking for the
    second stem of the same file is instant."""
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:24]
    v_path = storage.path_for("isolation_cache", f"{digest}_vocals.wav")
    b_path = storage.path_for("isolation_cache", f"{digest}_background.wav")
    if v_path.exists() and b_path.exists():
        vocals, sr = A.load_audio(v_path, sr=None)
        background, _ = A.load_audio(b_path, sr=None)
        return vocals, background, sr
    vocals, background, sr = get_engine("isolation").separate(path)
    A.save_wav(v_path, vocals, sr)
    A.save_wav(b_path, background, sr)
    return vocals, background, sr
