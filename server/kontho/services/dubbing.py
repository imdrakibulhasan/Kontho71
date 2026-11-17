"""Automatic dubbing: translate the speech in an audio/video file and re-voice it.

Pipeline
 1. extract audio                      (ffmpeg)
 2. split speech from background       (isolation engine, e.g. Demucs)
 3. transcribe + diarize speakers      (STT engine, e.g. faster-whisper + pyannote)
 4. translate every segment            (translation engine, e.g. NLLB-200 or an LLM)
 5. clone each speaker from their own lines and speak the translation, fitted to the original
    timing                              (TTS engine, e.g. OmniVoice with exact durations)
 6. re-mix with the original background and mux back into the video

Every segment is editable afterwards (text, translation, timing, voice) and can be re-rendered
individually - like a dubbing studio.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from .. import audio as A
from .. import db, jobs, storage
from ..engines import EngineUnavailable, get_engine
from ..engines.base import SynthesisOptions, VoiceSpec
from . import stt as S
from . import voices as V

log = logging.getLogger(__name__)
MIX_SR = 44100
CLONE_SR = 24000


def job_dir(dub_id: str) -> Path:
    return storage.dir_for("dubbing", dub_id)


def load_state(dub_id: str) -> dict[str, Any]:
    p = job_dir(dub_id) / "state.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else {}


def save_state(dub_id: str, state: dict[str, Any]) -> None:
    p = job_dir(dub_id) / "state.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(p)


# ------------------------------------------------------------------ public API
def create(source_path: Path, name: str, target_lang: str, source_lang: str | None = None,
           num_speakers: int = 0, voice_id: str | None = None, keep_background: bool = True) -> dict[str, Any]:
    dub_id = db.new_id("dub_")
    d = job_dir(dub_id)
    src = d / ("source" + source_path.suffix.lower())
    source_path.replace(src)
    params = {"source": str(src), "target_lang": target_lang, "source_lang": source_lang or None,
              "num_speakers": int(num_speakers or 0), "voice_id": voice_id or None,
              "keep_background": bool(keep_background), "is_video": A.has_video(src),
              "duration": A.probe_duration(src)}
    job = jobs.create("dubbing", name or source_path.name, params, job_id=dub_id)
    jobs.run(dub_id, _run_full)
    return job


def rerender(dub_id: str) -> None:
    db.update("jobs", dub_id, {"status": "queued", "progress": 0.0, "message": "Queued", "error": None,
                               "updated_at": db.now()})
    jobs.run(dub_id, _run_rerender)


def update_segment(dub_id: str, index: int, changes: dict[str, Any]) -> dict[str, Any]:
    state = load_state(dub_id)
    segs = state.get("segments", [])
    if not 0 <= index < len(segs):
        raise KeyError("segment not found")
    seg = segs[index]
    for key in ("text", "translation", "start", "end", "speaker", "voice_id"):
        if key in changes and changes[key] is not None:
            seg[key] = float(changes[key]) if key in ("start", "end") else changes[key]
    if seg["end"] <= seg["start"]:
        raise ValueError("end must be after start")
    if changes.get("retranslate"):
        seg["translation"] = get_engine("translate").translate([seg["text"]], state["source_lang"],
                                                               state["target_lang"])[0]
    seg["dirty"] = True
    save_state(dub_id, state)
    return seg


def to_api(job: dict[str, Any]) -> dict[str, Any]:
    status = {"queued": "dubbing", "running": "dubbing", "done": "dubbed", "failed": "failed"}[job["status"]]
    params = job.get("input") or {}
    state = load_state(job["id"])
    return {
        "dubbing_id": job["id"], "name": job["name"], "status": status, "progress": job["progress"],
        "message": job["message"], "error": job.get("error"),
        "source_language": state.get("source_lang") or params.get("source_lang"),
        "target_languages": [params.get("target_lang")], "is_video": params.get("is_video", False),
        "duration": params.get("duration"), "num_speakers": len(state.get("speakers", {})) or None,
        "created_at": job["created_at"], "updated_at": job["updated_at"],
    }


def output_file(dub_id: str, lang: str, prefer_video: bool = True) -> Path | None:
    d = job_dir(dub_id)
    for name in ([f"dubbed_{lang}.mp4"] if prefer_video else []) + [f"dubbed_{lang}.mp3", f"dubbed_{lang}.wav"]:
        if (d / name).exists():
            return d / name
    return None


def subtitles(dub_id: str, lang: str, fmt: str = "srt") -> str:
    state = load_state(dub_id)
    original = lang == state.get("source_lang") and lang != state.get("target_lang")
    segs = [{"start": s["start"], "end": s["end"], "text": s["text"] if original else s["translation"],
             "speaker_id": s["speaker"]} for s in state.get("segments", [])]
    return S.to_vtt(segs) if fmt in ("vtt", "webvtt") else S.to_srt(segs)


def delete(dub_id: str) -> bool:
    storage.remove_tree(job_dir(dub_id))
    return db.delete("jobs", dub_id)


# ------------------------------------------------------------------ pipeline
def _run_full(job: dict[str, Any], progress: jobs.Progress) -> dict[str, Any]:
    p = job["input"]
    dub_id = job["id"]
    d = job_dir(dub_id)

    progress(0.03, "Extracting audio")
    mix_audio, _ = A.load_audio(p["source"], sr=MIX_SR)
    A.save_wav(d / "original.wav", mix_audio, MIX_SR)

    progress(0.08, "Separating speech from background")
    try:
        vocals, background, sep_sr = get_engine("isolation").separate(d / "original.wav")
        vocals = A.resample(vocals, sep_sr, MIX_SR)
        background = A.resample(background, sep_sr, MIX_SR)
    except EngineUnavailable as exc:
        log.warning("Isolation engine unavailable (%s): background will not be preserved", exc)
        vocals, background = mix_audio, np.zeros_like(mix_audio)
    A.save_wav(d / "vocals.wav", vocals, MIX_SR)
    A.save_wav(d / "background.wav", background, MIX_SR)

    progress(0.25, "Transcribing and identifying speakers")
    n = p.get("num_speakers") or 0
    tr = S.transcribe(d / "vocals.wav", language=p.get("source_lang"), diarize=n != 1, num_speakers=n or None)
    source_lang = p.get("source_lang") or tr.language

    progress(0.42, "Translating")
    texts = [s.text for s in tr.segments]
    translations = get_engine("translate").translate(texts, source_lang, p["target_lang"]) if texts else []
    segments = [{"index": i, "start": round(s.start, 3), "end": round(s.end, 3), "speaker": s.speaker,
                 "text": s.text, "translation": t, "voice_id": None, "dirty": True}
                for i, (s, t) in enumerate(zip(tr.segments, translations))]
    state = {"source_lang": source_lang, "target_lang": p["target_lang"], "segments": segments,
             "speakers": {}, "duration": len(mix_audio) / MIX_SR}

    progress(0.5, "Cloning speaker voices")
    state["speakers"] = _build_speaker_refs(d, vocals, segments)
    save_state(dub_id, state)
    return _render(dub_id, state, p, progress, start=0.55)


def _run_rerender(job: dict[str, Any], progress: jobs.Progress) -> dict[str, Any]:
    state = load_state(job["id"])
    return _render(job["id"], state, job["input"], progress, start=0.05)


def _build_speaker_refs(d: Path, vocals: np.ndarray, segments: list[dict]) -> dict[str, dict]:
    """For every speaker, collect up to ~12 s of their cleanest lines as the cloning reference."""
    speakers: dict[str, dict] = {}
    by_spk: dict[str, list[dict]] = {}
    for s in segments:
        by_spk.setdefault(s["speaker"], []).append(s)
    for spk, segs in by_spk.items():
        chosen, total = [], 0.0
        for s in sorted(segs, key=lambda s: s["end"] - s["start"], reverse=True):
            dur = s["end"] - s["start"]
            if dur < 0.8:
                continue
            chosen.append(s)
            total += dur
            if total >= 12.0:
                break
        chosen = chosen or segs[:1]
        chosen.sort(key=lambda s: s["start"])
        clips = [A.resample(A.cut(vocals, MIX_SR, s["start"], s["end"]), MIX_SR, CLONE_SR) for s in chosen]
        ref = A.peak_normalize(A.concat(clips, CLONE_SR, gap=0.25))
        path = A.save_wav(d / "refs" / f"{spk}.wav", ref, CLONE_SR)
        speakers[spk] = {"ref_audio": str(path), "ref_text": " ".join(s["text"] for s in chosen),
                         "voice_id": None}
    return speakers


def _spec_for(seg: dict, state: dict, default_voice: str | None) -> VoiceSpec:
    vid = seg.get("voice_id") or state["speakers"].get(seg["speaker"], {}).get("voice_id") or default_voice
    if vid:
        v = V.get_voice(vid)
        if v:
            return V.voice_spec(v)
    spk = state["speakers"].get(seg["speaker"]) or next(iter(state["speakers"].values()), {})
    return VoiceSpec(ref_audio=spk.get("ref_audio"), ref_text=spk.get("ref_text"), seed=1234)


def _render(dub_id: str, state: dict, params: dict, progress: jobs.Progress, start: float) -> dict[str, Any]:
    d = job_dir(dub_id)
    engine = get_engine("tts")
    segs = state["segments"]
    todo = [s for s in segs if s.get("dirty") or not (d / "clips" / f"{s['index']}.wav").exists()]
    for k, seg in enumerate(todo):
        progress(start + (0.9 - start) * k / max(1, len(todo)), f"Voicing segment {k + 1}/{len(todo)}")
        # allow a line to run slightly into the following pause, never into the next line
        nxt = next((s["start"] for s in segs if s["start"] >= seg["end"] - 1e-3 and s is not seg), None)
        slot = seg["end"] - seg["start"]
        room = slot if nxt is None else max(slot, min(nxt - seg["start"], slot * 1.25))
        opts = SynthesisOptions(language=state["target_lang"], steps=32, guidance=3.0,
                                duration=slot if engine.supports_duration else None)
        clip, sr = engine.synthesize(seg["translation"], _spec_for(seg, state, params.get("voice_id")), opts)
        clip = A.fit_to_duration(A.resample(clip, sr, MIX_SR), MIX_SR, room)
        A.save_wav(d / "clips" / f"{seg['index']}.wav", clip, MIX_SR)
        seg["dirty"] = False
        save_state(dub_id, state)

    progress(0.92, "Mixing")
    total = state.get("duration") or params.get("duration") or 0
    out = A.silence(total, MIX_SR)
    for seg in segs:
        clip, _ = A.load_audio(d / "clips" / f"{seg['index']}.wav", sr=MIX_SR)
        out = A.overlay(out, clip, MIX_SR, seg["start"])
    if params.get("keep_background", True) and (d / "background.wav").exists():
        bg, _ = A.load_audio(d / "background.wav", sr=MIX_SR)
        out = A.mix(out, bg)
    out = A.peak_normalize(out, 0.95)
    lang = state["target_lang"]
    wav = A.save_wav(d / f"dubbed_{lang}.wav", out, MIX_SR)
    (d / f"dubbed_{lang}.mp3").write_bytes(A.encode(out, MIX_SR, "mp3_44100_192"))
    if params.get("is_video"):
        progress(0.96, "Muxing video")
        A.mux_video(params["source"], wav, d / f"dubbed_{lang}.mp4")
    (d / f"subtitles_{lang}.srt").write_text(subtitles(dub_id, lang), "utf-8")
    return {"target_lang": lang, "segments": len(segs)}
