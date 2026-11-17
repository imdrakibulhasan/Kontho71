"""Voice library: premade (designed) voices, instant voice cloning and voice design."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

from .. import audio as A
from .. import db, storage
from .. import emotions as E
from ..engines import get_engine
from ..engines.base import SynthesisOptions, VoiceSpec
from ..voice_design import normalize as normalize_instruct

CLONE_SR = 24000
MAX_REF_SECONDS = 15.0

# Premade voices are defined by a voice-design prompt plus a fixed seed so they stay consistent.
# For the most consistent results (and always for Bengali), clone a voice instead.
PREMADE: list[dict[str, Any]] = [
    {"id": "premade_aria", "name": "Aria", "instruct": "female, young adult, moderate pitch, american accent",
     "seed": 11, "labels": {"gender": "female", "age": "young", "accent": "american", "use_case": "narration"}},
    {"id": "premade_roger", "name": "Roger", "instruct": "male, middle-aged, low pitch, american accent",
     "seed": 23, "labels": {"gender": "male", "age": "middle_aged", "accent": "american", "use_case": "conversational"}},
    {"id": "premade_sarah", "name": "Sarah", "instruct": "female, middle-aged, low pitch, british accent",
     "seed": 37, "labels": {"gender": "female", "age": "middle_aged", "accent": "british", "use_case": "audiobook"}},
    {"id": "premade_liam", "name": "Liam", "instruct": "male, young adult, moderate pitch, australian accent",
     "seed": 41, "labels": {"gender": "male", "age": "young", "accent": "australian", "use_case": "social_media"}},
    {"id": "premade_priya", "name": "Priya", "instruct": "female, young adult, high pitch, indian accent",
     "seed": 47, "labels": {"gender": "female", "age": "young", "accent": "indian", "use_case": "conversational"}},
    {"id": "premade_arjun", "name": "Arjun", "instruct": "male, middle-aged, moderate pitch, indian accent",
     "seed": 59, "labels": {"gender": "male", "age": "middle_aged", "accent": "indian", "use_case": "news"}},
    {"id": "premade_grace", "name": "Grace", "instruct": "female, elderly, moderate pitch, british accent",
     "seed": 53, "labels": {"gender": "female", "age": "old", "accent": "british", "use_case": "storytelling"}},
    {"id": "premade_george", "name": "George", "instruct": "male, elderly, very low pitch, british accent",
     "seed": 67, "labels": {"gender": "male", "age": "old", "accent": "british", "use_case": "narration"}},
    {"id": "premade_mia", "name": "Mia", "instruct": "female, child, high pitch",
     "seed": 71, "labels": {"gender": "female", "age": "child", "use_case": "characters"}},
    {"id": "premade_leo", "name": "Leo", "instruct": "male, young adult, whisper",
     "seed": 83, "labels": {"gender": "male", "age": "young", "use_case": "asmr"}},
]


def seed_premade() -> None:
    existing = {v["id"]: v for v in db.query("SELECT id, instruct FROM voices WHERE category = 'premade'")}
    for v in PREMADE:
        if v["id"] in existing and existing[v["id"]]["instruct"] != v["instruct"]:
            db.update("voices", v["id"], {"instruct": v["instruct"], "labels": v["labels"], "preview": None,
                                          "description": f"Designed voice: {v['instruct']}"})
        if v["id"] not in existing:
            db.insert("voices", {"id": v["id"], "name": v["name"], "category": "premade",
                                 "description": f"Designed voice: {v['instruct']}", "labels": v["labels"],
                                 "instruct": v["instruct"], "settings": {"seed": v["seed"]},
                                 "created_at": db.now()})


def to_api(v: dict[str, Any]) -> dict[str, Any]:
    """ElevenLabs-compatible voice object (plus Kontho's ``emotions``)."""
    return {
        "emotions": sorted(list_emotions(v["id"])),
        "voice_id": v["id"],
        "name": v["name"],
        "category": v["category"],
        "description": v.get("description") or "",
        "labels": v.get("labels") or {},
        "language": v.get("language") or "",
        "preview_url": f"/v1/voices/{v['id']}/preview",
        "settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "speed": 1.0,
                     "use_speaker_boost": True},
        "fine_tuning": {"is_allowed_to_fine_tune": False},
        "available_for_tiers": [],
        "created_at_unix": int(v["created_at"]),
    }


def list_voices(search: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM voices WHERE 1=1", []
    if search:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY CASE category WHEN 'premade' THEN 1 ELSE 0 END, CASE category WHEN 'premade' THEN created_at ELSE -created_at END"
    return db.query(sql, params)


def get_voice(voice_id: str) -> dict[str, Any] | None:
    return db.get("voices", voice_id)


def voice_spec(v: dict[str, Any], anchored: bool = True) -> VoiceSpec:
    """How to synthesize a voice. Prompt-only (premade) voices are *anchored*: their preview clip,
    generated once from the design prompt, is used as a cloning reference so the timbre stays
    identical across sentences and requests."""
    seed = (v.get("settings") or {}).get("seed")
    ref = v.get("ref_audio")
    if ref and not Path(ref).exists():
        ref = None
    if not ref and anchored and v.get("instruct"):
        return VoiceSpec(ref_audio=str(ensure_preview(v)), ref_text=PREVIEW_TEXT, seed=seed)
    return VoiceSpec(ref_audio=ref, ref_text=v.get("ref_text"), instruct=v.get("instruct"), seed=seed)


def _best_window(audio: np.ndarray, sr: int, seconds: float) -> np.ndarray:
    """Pick the loudest ``seconds``-long window (avoids long silences in the reference)."""
    n = int(seconds * sr)
    if audio.size <= n:
        return audio
    hop = sr // 2
    energy = [float(np.mean(audio[i:i + n] ** 2)) for i in range(0, audio.size - n, hop)]
    start = int(np.argmax(energy)) * hop
    return audio[start:start + n]


def prepare_reference(paths: list[Path], dest: Path, remove_noise: bool = False) -> tuple[Path, float]:
    clips = []
    for p in paths:
        if remove_noise:
            vocals, _, sr = get_engine("isolation").separate(p)
            clips.append(A.resample(vocals, sr, CLONE_SR))
        else:
            clips.append(A.load_audio(p, sr=CLONE_SR)[0])
    audio = A.concat(clips, CLONE_SR, gap=0.3)
    audio = A.peak_normalize(_best_window(audio, CLONE_SR, MAX_REF_SECONDS))
    if audio.size < CLONE_SR * 2:
        raise ValueError("Reference audio is too short: provide at least 3 seconds of clear speech.")
    A.save_wav(dest, audio, CLONE_SR)
    return dest, audio.size / CLONE_SR


def create_clone(name: str, files: list[Path], description: str = "", labels: dict | None = None,
                 ref_text: str | None = None, language: str = "", remove_noise: bool = False) -> dict[str, Any]:
    vid = db.new_id("v_")
    ref_path, _ = prepare_reference(files, storage.path_for("voices", vid, "reference.wav"), remove_noise)
    if not ref_text:
        try:
            tr = get_engine("stt").transcribe(ref_path, language=language or None)
            ref_text = tr.text
            language = language or tr.language
        except Exception:  # the TTS engine can still auto-transcribe / work without it
            ref_text = None
    voice = {"id": vid, "name": name, "category": "cloned", "description": description, "labels": labels or {},
             "language": language, "ref_audio": str(ref_path), "ref_text": ref_text, "preview": str(ref_path),
             "settings": {}, "created_at": db.now()}
    db.insert("voices", voice)
    return voice


def design_previews(description: str, text: str, language: str | None = None, count: int = 3,
                    seed: int | None = None) -> list[dict[str, Any]]:
    """Generate ``count`` candidate voices from a text description (voice design)."""
    engine = get_engine("tts")
    if not engine.supports_design:
        raise ValueError(f"The '{engine.name}' TTS engine does not support voice design")
    instruct, ignored = normalize_instruct(description)
    if not instruct:
        raise ValueError("Describe the voice with: gender, age, pitch, accent or whisper "
                         "(e.g. 'female, elderly, low pitch, british accent')")
    base_seed = seed if seed is not None else int(db.now()) % 100000
    out = []
    for i in range(count):
        gid = db.new_id("gen_")
        audio, sr = engine.synthesize(text, VoiceSpec(instruct=instruct),
                                      SynthesisOptions(language=language, seed=base_seed + i))
        path = A.save_wav(storage.path_for("designs", f"{gid}.wav"), audio, sr)
        db.insert("history", {"id": gid, "kind": "design", "text": text, "voice_name": description,
                              "settings": {"description": instruct, "language": language, "seed": base_seed + i},
                              "audio": str(path), "content_type": "audio/wav", "characters": len(text),
                              "created_at": db.now()})
        out.append({"generated_voice_id": gid, "audio_url": f"/v1/history/{gid}/audio",
                    "duration_secs": round(audio.size / sr, 2), "seed": base_seed + i,
                    "instruct": instruct, "ignored_terms": ignored})
    return out


def save_designed(generated_voice_id: str, name: str, description: str = "",
                  labels: dict | None = None) -> dict[str, Any]:
    """Keep a design preview as a permanent voice: its clip becomes the cloning reference."""
    gen = db.get("history", generated_voice_id)
    if not gen or gen["kind"] != "design":
        raise KeyError("Unknown generated_voice_id")
    vid = db.new_id("v_")
    ref = storage.path_for("voices", vid, "reference.wav")
    audio, _ = A.load_audio(gen["audio"], sr=CLONE_SR)
    A.save_wav(ref, audio, CLONE_SR)
    s = gen["settings"]
    voice = {"id": vid, "name": name, "category": "designed", "description": description or s.get("description", ""),
             "labels": labels or {}, "language": s.get("language") or "", "ref_audio": str(ref),
             "ref_text": gen["text"], "instruct": s.get("description"), "preview": str(ref),
             "settings": {"seed": s.get("seed")}, "created_at": db.now()}
    db.insert("voices", voice)
    return voice


PREVIEW_TEXT = "Hello! This is a preview of my voice. I hope you like how I sound."


def ensure_preview(v: dict[str, Any]) -> Path:
    if v.get("preview") and Path(v["preview"]).exists():
        return Path(v["preview"])
    spec = voice_spec(v, anchored=False)
    audio, sr = get_engine("tts").synthesize(PREVIEW_TEXT, spec, SynthesisOptions(language="en", seed=spec.seed))
    path = A.save_wav(storage.path_for("voices", v["id"], "preview.wav"), audio, sr)
    db.update("voices", v["id"], {"preview": str(path)})
    v["preview"] = str(path)
    return path


def update_voice(voice_id: str, fields: dict[str, Any]) -> None:
    allowed = {k: v for k, v in fields.items() if k in {"name", "description", "labels", "language", "ref_text"}}
    if allowed:
        db.update("voices", voice_id, allowed)


def delete_voice(voice_id: str) -> bool:
    v = db.get("voices", voice_id)
    if not v or v["category"] == "premade":
        return False
    storage.remove_tree(storage.path_for("voices", voice_id, "x").parent)
    for row in db.query("SELECT id FROM voice_emotions WHERE voice_id = ?", (voice_id,)):
        db.delete("voice_emotions", row["id"])
    return db.delete("voices", voice_id)


# ------------------------------------------------------------------ emotions
def list_emotions(voice_id: str) -> dict[str, dict[str, Any]]:
    rows = db.query("SELECT * FROM voice_emotions WHERE voice_id = ? ORDER BY emotion", (voice_id,))
    return {r["emotion"]: r for r in rows if Path(r["ref_audio"]).exists()}


def set_emotion(voice_id: str, emotion: str, files: list[Path], ref_text: str | None = None,
                remove_noise: bool = False, language: str | None = None) -> dict[str, Any]:
    """Store (or replace) the reference clip a voice uses for one emotion."""
    emo = E.canonical(emotion)
    if not emo:
        raise ValueError(f"Unknown emotion '{emotion}'. Known: {', '.join(E.EMOTIONS)}")
    if not get_voice(voice_id):
        raise KeyError(f"Voice '{voice_id}' not found")
    dest = storage.path_for("voices", voice_id, "emotions", f"{emo}.wav")
    prepare_reference(files, dest, remove_noise)
    if not ref_text:
        try:
            ref_text = get_engine("stt").transcribe(dest, language=language or None).text
        except Exception:
            ref_text = None
    old = db.query("SELECT id FROM voice_emotions WHERE voice_id = ? AND emotion = ?", (voice_id, emo))
    for row in old:
        db.delete("voice_emotions", row["id"])
    row = {"id": db.new_id("emo_"), "voice_id": voice_id, "emotion": emo, "ref_audio": str(dest),
           "ref_text": ref_text, "created_at": db.now()}
    db.insert("voice_emotions", row)
    return row


def delete_emotion(voice_id: str, emotion: str) -> bool:
    rows = db.query("SELECT * FROM voice_emotions WHERE voice_id = ? AND emotion = ?",
                    (voice_id, E.canonical(emotion) or emotion))
    for r in rows:
        Path(r["ref_audio"]).unlink(missing_ok=True)
        db.delete("voice_emotions", r["id"])
    return bool(rows)


def emotion_spec(v: dict[str, Any], emotion: str | None) -> tuple[VoiceSpec, str | None]:
    """Voice spec for an emotion: its own clip, else a related emotion's clip, else the base voice.
    Returns (spec, emotion actually used or None)."""
    base = voice_spec(v)
    if not emotion or emotion == "neutral":
        return base, None
    clips = list_emotions(v["id"])
    used = E.resolve(emotion, set(clips))
    if not used:
        return base, None
    clip = clips[used]
    return VoiceSpec(ref_audio=clip["ref_audio"], ref_text=clip["ref_text"], seed=base.seed), used


# ------------------------------------------------------------------ emotion packs
def _read_transcripts(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for tf in folder.rglob("transcripts.txt"):
        for line in tf.read_text("utf-8").splitlines():
            m = re.match(r"\s*([^\t:|]+?\.(?:mp3|wav|m4a|ogg|flac|webm))\s*[\t:|]\s*(.+)$", line, re.I)
            if m:
                out[Path(m.group(1)).stem.lower()] = re.sub(r"\[[^\]]*\]", " ", m.group(2)).strip()
    return out


def import_pack(folder: Path, language: str = "") -> list[dict[str, Any]]:
    """Import ``<voice>_<emotion>.<ext>`` clips (+ optional transcripts.txt) as voices with emotions.

    The voice's normal reference is its ``neutral`` clip (else calm, warm, or its longest clip).
    Voices are matched by name, so re-importing a pack updates them instead of duplicating."""
    texts = _read_transcripts(folder)
    groups: dict[str, dict[str, Path]] = {}
    for f in sorted(folder.rglob("*")):
        if f.suffix.lower() not in {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"} or "_" not in f.stem:
            continue
        who, raw = f.stem.rsplit("_", 1)
        emo = E.canonical(re.sub(r"\d+$", "", raw))
        if not emo:
            continue
        key = who.strip().lower()
        prev = groups.setdefault(key, {}).get(emo)
        if prev is None or A.probe_duration(f) > A.probe_duration(prev):  # keep the longest take
            groups[key][emo] = f
    result = []
    for key, clips in groups.items():
        name = key.replace("-", " ").replace("_", " ").title()
        base_emo = next((e for e in ("neutral", "calm", "warm") if e in clips),
                        max(clips, key=lambda e: A.probe_duration(clips[e])))
        existing = db.query("SELECT * FROM voices WHERE lower(name) = ? AND category = 'cloned'", (name.lower(),))
        if existing:
            voice = existing[0]
            prepare_reference([clips[base_emo]], Path(voice["ref_audio"]))
            db.update("voices", voice["id"], {"ref_text": texts.get(clips[base_emo].stem.lower())})
        else:
            voice = create_clone(name, [clips[base_emo]], description="Imported emotion pack",
                                 labels={"source": "emotion pack"}, language=language,
                                 ref_text=texts.get(clips[base_emo].stem.lower()) or None)
        for emo, path in clips.items():
            if emo != "neutral":
                set_emotion(voice["id"], emo, [path], texts.get(path.stem.lower()) or None, language=language)
        result.append({"voice_id": voice["id"], "name": name, "base": base_emo,
                       "emotions": sorted(e for e in clips if e != "neutral")})
    if not result:
        raise ValueError("No clips named <voice>_<emotion>.mp3 with a known emotion were found")
    return result
