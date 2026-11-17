"""Engine registry: engines are created lazily (models load on first use) and cached."""

from __future__ import annotations

import importlib
import threading
from typing import Any

from ..config import get_settings

REGISTRY: dict[str, dict[str, str]] = {
    "tts": {
        "omnivoice": "kontho.engines.omnivoice_tts:OmniVoiceTTS",
        "mock": "kontho.engines.mock:MockTTS",
    },
    "stt": {
        "whisper": "kontho.engines.whisper_stt:WhisperSTT",
        "mock": "kontho.engines.mock:MockSTT",
    },
    "sfx": {
        "audioldm2": "kontho.engines.diffusers_sfx:DiffusersSFX",
        "stable-audio": "kontho.engines.diffusers_sfx:DiffusersSFX",
        "mock": "kontho.engines.mock:MockSFX",
    },
    "isolation": {
        "demucs": "kontho.engines.demucs_isolation:DemucsIsolation",
        "mock": "kontho.engines.mock:MockIsolation",
    },
    "translate": {
        "nllb": "kontho.engines.translate:NLLBTranslate",
        "llm": "kontho.engines.translate:LLMTranslate",
        "mock": "kontho.engines.mock:MockTranslate",
    },
}

_cache: dict[str, Any] = {}
_lock = threading.Lock()


class EngineUnavailable(RuntimeError):
    pass


def selected(kind: str) -> str:
    s = get_settings()
    return {"tts": s.tts_engine, "stt": s.stt_engine, "sfx": s.sfx_engine,
            "isolation": s.isolation_engine, "translate": s.translate_engine}[kind]


def register(kind: str, name: str, target: str) -> None:
    """Register a third-party engine, e.g. ``register("tts", "myengine", "pkg.module:Class")``."""
    REGISTRY.setdefault(kind, {})[name] = target


def get_engine(kind: str):
    name = selected(kind)
    key = f"{kind}:{name}"
    if key in _cache:
        return _cache[key]
    with _lock:
        if key in _cache:
            return _cache[key]
        target = REGISTRY.get(kind, {}).get(name)
        if not target:
            raise EngineUnavailable(f"Unknown {kind} engine '{name}'. Available: {', '.join(REGISTRY.get(kind, {}))}")
        mod_name, cls_name = target.split(":")
        try:
            engine = getattr(importlib.import_module(mod_name), cls_name)()
        except ImportError as exc:
            raise EngineUnavailable(
                f"The '{name}' {kind} engine is not installed ({exc}). Install it with: pip install 'kontho[{kind}]'"
            ) from exc
        _cache[key] = engine
        return engine


def status() -> dict[str, dict[str, Any]]:
    return {kind: {"engine": selected(kind), "loaded": f"{kind}:{selected(kind)}" in _cache,
                   "available": list(REGISTRY[kind])} for kind in REGISTRY}
