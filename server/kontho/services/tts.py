"""Text-to-speech: chunking, voice settings, history, streaming and timestamps."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Iterator

import numpy as np

from .. import audio as A
from .. import db, storage
from ..engines import get_engine
from ..engines.base import SynthesisOptions
from ..text import apply_pronunciations, chunk_text
from . import voices as V

# Model ids: "quality" vs "turbo" trade quality for speed. ElevenLabs ids are accepted as aliases.
MODELS = [
    {"model_id": "kontho_v1", "name": "Kontho v1 (quality)", "description": "Best quality, 32 sampling steps.",
     "steps": 32, "can_do_text_to_speech": True, "can_do_voice_conversion": True, "max_characters_request": 50000},
    {"model_id": "kontho_turbo", "name": "Kontho Turbo", "description": "About 2x faster, 16 sampling steps.",
     "steps": 16, "can_do_text_to_speech": True, "can_do_voice_conversion": True, "max_characters_request": 50000},
]
_ALIASES = {"flash": "kontho_turbo", "turbo": "kontho_turbo"}
MAX_CHARS = 50000


def model_steps(model_id: str | None) -> int:
    mid = (model_id or "kontho_v1").lower()
    for m in MODELS:
        if m["model_id"] == mid:
            return m["steps"]
    return 16 if any(k in mid for k in _ALIASES) else 32


@dataclass
class VoiceSettings:
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speed: float = 1.0
    use_speaker_boost: bool = True

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "VoiceSettings":
        d = d or {}
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d and d[k] is not None})


def make_options(settings: VoiceSettings, voice_seed: int | None, language: str | None,
                 model_id: str | None, seed: int | None, chunk_index: int = 0) -> SynthesisOptions:
    # similarity_boost -> guidance (how strongly to follow the reference voice / prompt)
    guidance = 1.5 + 2.0 * max(0.0, min(1.0, settings.similarity_boost))
    # stability: high = deterministic (fixed seed), low = more expressive variation between takes
    if seed is None and settings.stability >= 0.5 and voice_seed is not None:
        seed = voice_seed
    if seed is not None:
        seed = seed + chunk_index if settings.stability < 0.5 else seed
    return SynthesisOptions(language=language or None, speed=max(0.5, min(2.0, settings.speed)), seed=seed,
                            guidance=guidance, steps=model_steps(model_id))


def _pronunciation_rules(language: str | None) -> list[dict]:
    return db.query("SELECT term, replacement FROM pronunciation WHERE language = '' OR language = ?",
                    (language or "",))


def resolve_voice(voice_id: str) -> dict[str, Any]:
    v = V.get_voice(voice_id)
    if not v:
        raise KeyError(f"Voice '{voice_id}' not found")
    return v


def iter_chunks(text: str, voice: dict[str, Any], settings: VoiceSettings, language: str | None,
                model_id: str | None, seed: int | None) -> Iterator[tuple[str, np.ndarray, int]]:
    text = apply_pronunciations(text, _pronunciation_rules(language))
    engine = get_engine("tts")
    spec = V.voice_spec(voice)
    for i, chunk in enumerate(chunk_text(text)):
        audio, sr = engine.synthesize(chunk, spec, make_options(settings, spec.seed, language, model_id, seed, i))
        yield chunk, audio, sr


def synthesize(text: str, voice_id: str, settings: dict | None = None, language: str | None = None,
               model_id: str | None = None, seed: int | None = None,
               save: bool = True) -> tuple[np.ndarray, int, list[tuple[str, float, float]], str | None]:
    """Return (audio, sr, [(chunk_text, start, end)], history_id)."""
    if not text.strip():
        raise ValueError("text is empty")
    if len(text) > MAX_CHARS:
        raise ValueError(f"text is longer than {MAX_CHARS} characters")
    voice = resolve_voice(voice_id)
    vs = VoiceSettings.from_dict(settings)
    parts, spans, sr, t = [], [], 24000, 0.0
    gap = 0.18
    for chunk, audio, sr in iter_chunks(text, voice, vs, language, model_id, seed):
        parts.append(audio)
        spans.append((chunk, t, t + audio.size / sr))
        t += audio.size / sr + gap
    out = A.concat(parts, sr, gap=gap)
    hid = None
    if save:
        hid = save_history("tts", out, sr, text=text, voice=voice,
                           settings={"voice_settings": vs.__dict__, "model_id": model_id, "language": language,
                                     "seed": seed})
    return out, sr, spans, hid


def save_history(kind: str, audio: np.ndarray, sr: int, text: str = "", voice: dict | None = None,
                 settings: dict | None = None) -> str:
    hid = db.new_id("h_")
    path = A.save_wav(storage.path_for("history", f"{hid}.wav"), audio, sr)
    db.insert("history", {"id": hid, "kind": kind, "voice_id": voice and voice["id"],
                          "voice_name": voice and voice["name"], "text": text, "settings": settings or {},
                          "audio": str(path), "content_type": "audio/wav", "characters": len(text or ""),
                          "created_at": db.now()})
    return hid


def stream(text: str, voice_id: str, settings: dict | None, language: str | None, model_id: str | None,
           seed: int | None, output_format: str) -> Iterator[bytes]:
    """Stream encoded audio chunk by chunk (sentence-level streaming)."""
    voice = resolve_voice(voice_id)
    vs = VoiceSettings.from_dict(settings)
    fmt = A.parse_output_format(output_format)
    collected, sr = [], 24000
    for _, audio, sr in iter_chunks(text, voice, vs, language, model_id, seed):
        piece = A.concat([audio, A.silence(0.18, sr)], sr)
        collected.append(piece)
        if fmt.codec == "wav":  # a WAV header can't be streamed per chunk -> send raw PCM after a header
            fmt = A.OutputFormat("pcm", fmt.sample_rate)
        yield A.encode(piece, sr, fmt)
    if collected:
        save_history("tts", np.concatenate(collected), sr, text=text, voice=voice,
                     settings={"voice_settings": vs.__dict__, "model_id": model_id, "language": language})


def alignment(spans: list[tuple[str, float, float]]) -> dict[str, list]:
    """Approximate character timings: each chunk's duration is spread over its characters."""
    chars, starts, ends = [], [], []
    for idx, (chunk, a, b) in enumerate(spans):
        text = chunk + (" " if idx < len(spans) - 1 else "")
        weights = [0.3 if c.isspace() else 1.0 for c in text]
        total = sum(weights) or 1.0
        t = a
        for c, w in zip(text, weights):
            d = (b - a) * w / total
            chars.append(c)
            starts.append(round(t, 3))
            ends.append(round(t + d, 3))
            t += d
    return {"characters": chars, "character_start_times_seconds": starts, "character_end_times_seconds": ends}


def with_timestamps(text: str, voice_id: str, settings: dict | None, language: str | None, model_id: str | None,
                    seed: int | None, output_format: str) -> dict[str, Any]:
    audio, sr, spans, _ = synthesize(text, voice_id, settings, language, model_id, seed)
    al = alignment(spans)
    return {"audio_base64": base64.b64encode(A.encode(audio, sr, output_format)).decode(),
            "alignment": al, "normalized_alignment": al}
