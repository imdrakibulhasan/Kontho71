"""Speech-to-text with word timestamps, speaker labels and subtitle export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..engines import get_engine
from ..engines.base import Transcript


def transcribe(path: Path, language: str | None = None, diarize: bool = False,
               num_speakers: int | None = None) -> Transcript:
    return get_engine("stt").transcribe(path, language=language, diarize=diarize, num_speakers=num_speakers)


def to_api(tr: Transcript) -> dict[str, Any]:
    """ElevenLabs-compatible speech-to-text response (plus ``segments``)."""
    words: list[dict[str, Any]] = []
    for seg in tr.segments:
        seg_words = seg.words or [type("W", (), {"text": seg.text, "start": seg.start, "end": seg.end})()]
        for i, w in enumerate(seg_words):
            if words:
                prev_end = words[-1]["end"]
                words.append({"text": " ", "start": prev_end, "end": w.start, "type": "spacing",
                              "speaker_id": seg.speaker})
            words.append({"text": w.text, "start": round(w.start, 3), "end": round(w.end, 3), "type": "word",
                          "speaker_id": seg.speaker})
    return {
        "language_code": tr.language,
        "language_probability": 1.0,
        "text": tr.text,
        "words": words,
        "segments": [{"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text, "speaker_id": s.speaker}
                     for s in tr.segments],
        "duration": round(tr.duration, 3),
    }


def _ts(t: float, sep: str) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(segments: list[dict[str, Any]], speakers: bool = False) -> str:
    lines = []
    for i, s in enumerate(segments, 1):
        text = s["text"]
        if speakers and s.get("speaker_id"):
            text = f"[{s['speaker_id']}] {text}"
        lines.append(f"{i}\n{_ts(s['start'], ',')} --> {_ts(s['end'], ',')}\n{text}\n")
    return "\n".join(lines)


def to_vtt(segments: list[dict[str, Any]]) -> str:
    body = "\n".join(f"{_ts(s['start'], '.')} --> {_ts(s['end'], '.')}\n{s['text']}\n" for s in segments)
    return "WEBVTT\n\n" + body
