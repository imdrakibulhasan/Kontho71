"""REST API. Paths and payloads follow the ElevenLabs API so official SDKs and existing
integrations work by pointing their base URL at a Kontho server."""

from __future__ import annotations

import base64
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from .. import __version__, db
from .. import audio as A
from .. import engines as E
from .. import emotions as EM
from ..languages import language_list
from ..services import changer, dubbing, sfx, stt
from ..services import tts as T
from ..services import voices as V
from .deps import (audio_response, errors, new_api_key, parse_json_field, require_api_key, save_uploads)

router = APIRouter(dependencies=[Depends(require_api_key)])


# =============================================================== text to speech
class TTSRequest(BaseModel):
    text: str
    model_id: str | None = "kontho_v1"
    language_code: str | None = None
    voice_settings: dict[str, Any] | None = None
    seed: int | None = None
    previous_text: str | None = None
    next_text: str | None = None
    emotion: str | None = None  # default emotion for text before the first [emotion] tag


@router.post("/v1/text-to-speech/{voice_id}", tags=["Text to speech"])
def text_to_speech(voice_id: str, body: TTSRequest, output_format: str = Query("mp3_44100_128")):
    report: list = []
    with errors():
        audio, sr, _, hid = T.synthesize(body.text, voice_id, body.voice_settings, body.language_code,
                                         body.model_id, body.seed, emotion=body.emotion, report=report)
    resp = audio_response(audio, sr, output_format, hid, "speech")
    if report:
        resp.headers["emotions-used"] = T.emotion_header(report)
    return resp


@router.post("/v1/text-to-speech/{voice_id}/stream", tags=["Text to speech"])
def text_to_speech_stream(voice_id: str, body: TTSRequest, output_format: str = Query("mp3_44100_128")):
    with errors():
        T.resolve_voice(voice_id)
        fmt = A.parse_output_format(output_format)
    gen = T.stream(body.text, voice_id, body.voice_settings, body.language_code, body.model_id, body.seed,
                   output_format, body.emotion)
    media = "audio/pcm" if fmt.codec == "wav" else fmt.content_type
    return StreamingResponse(gen, media_type=media)


@router.post("/v1/text-to-speech/{voice_id}/with-timestamps", tags=["Text to speech"])
def text_to_speech_timestamps(voice_id: str, body: TTSRequest, output_format: str = Query("mp3_44100_128")):
    with errors():
        return T.with_timestamps(body.text, voice_id, body.voice_settings, body.language_code, body.model_id,
                                 body.seed, output_format, body.emotion)


# =============================================================== voices
@router.get("/v1/voices", tags=["Voices"])
def list_voices(search: str | None = None, category: str | None = None):
    return {"voices": [V.to_api(v) for v in V.list_voices(search, category)]}


@router.get("/v2/voices", tags=["Voices"])
def list_voices_v2(search: str | None = None, category: str | None = None, page_size: int = 100):
    vs = V.list_voices(search, category)
    return {"voices": [V.to_api(v) for v in vs[:page_size]], "has_more": len(vs) > page_size,
            "total_count": len(vs), "next_page_token": None}


@router.get("/v1/voices/settings/default", tags=["Voices"])
def default_voice_settings():
    return T.VoiceSettings().__dict__


@router.get("/v1/voices/{voice_id}", tags=["Voices"])
def get_voice(voice_id: str):
    v = V.get_voice(voice_id)
    if not v:
        raise HTTPException(404, {"status": "voice_not_found", "message": "Voice not found"})
    return V.to_api(v)


@router.get("/v1/voices/{voice_id}/preview", tags=["Voices"])
def voice_preview(voice_id: str):
    v = V.get_voice(voice_id)
    if not v:
        raise HTTPException(404, {"status": "voice_not_found", "message": "Voice not found"})
    with errors():
        path = V.ensure_preview(v)
    return FileResponse(path, media_type="audio/wav")


@router.post("/v1/voices/add", tags=["Voices"])
def add_voice(name: str = Form(...), files: list[UploadFile] = File(...), description: str = Form(""),
              labels: str | None = Form(None), remove_background_noise: bool = Form(False),
              reference_text: str | None = Form(None), language: str = Form("")):
    paths = save_uploads(files, db.new_id("clone_"))
    with errors():
        v = V.create_clone(name, paths, description, parse_json_field(labels, "labels"), reference_text,
                           language, remove_background_noise)
    return {"voice_id": v["id"], "requires_verification": False}


@router.post("/v1/voices/{voice_id}/edit", tags=["Voices"])
def edit_voice(voice_id: str, name: str | None = Form(None), description: str | None = Form(None),
               labels: str | None = Form(None), reference_text: str | None = Form(None)):
    if not V.get_voice(voice_id):
        raise HTTPException(404, {"status": "voice_not_found", "message": "Voice not found"})
    fields: dict[str, Any] = {"name": name, "description": description, "ref_text": reference_text}
    if labels is not None:
        fields["labels"] = parse_json_field(labels, "labels")
    V.update_voice(voice_id, {k: v for k, v in fields.items() if v is not None})
    return {"status": "ok"}


@router.delete("/v1/voices/{voice_id}", tags=["Voices"])
def delete_voice(voice_id: str):
    if not V.delete_voice(voice_id):
        raise HTTPException(404, {"status": "voice_not_found", "message": "Voice not found or not deletable"})
    return {"status": "ok"}


# =============================================================== emotions
@router.get("/v1/emotions", tags=["Emotions"])
def emotion_catalog():
    """Emotion tags understood in text (``[angry] ...``), with accepted aliases."""
    return {"emotions": EM.catalog()}


@router.get("/v1/voices/{voice_id}/emotions", tags=["Emotions"])
def voice_emotions(voice_id: str):
    if not V.get_voice(voice_id):
        raise HTTPException(404, {"status": "voice_not_found", "message": "Voice not found"})
    return {"emotions": [{"emotion": e, "reference_text": r["ref_text"],
                          "audio_url": f"/v1/voices/{voice_id}/emotions/{e}/audio"}
                         for e, r in V.list_emotions(voice_id).items()]}


@router.post("/v1/voices/{voice_id}/emotions", tags=["Emotions"])
def add_voice_emotion(voice_id: str, emotion: str = Form(...), files: list[UploadFile] = File(...),
                      reference_text: str | None = Form(None), remove_background_noise: bool = Form(False),
                      language: str | None = Form(None)):
    paths = save_uploads(files, db.new_id("emo_"))
    with errors():
        row = V.set_emotion(voice_id, emotion, paths, reference_text, remove_background_noise, language)
    return {"emotion": row["emotion"], "reference_text": row["ref_text"]}


@router.get("/v1/voices/{voice_id}/emotions/{emotion}/audio", tags=["Emotions"])
def voice_emotion_audio(voice_id: str, emotion: str):
    clip = V.list_emotions(voice_id).get(emotion)
    if not clip:
        raise HTTPException(404, {"status": "not_found", "message": "No clip for this emotion"})
    return FileResponse(clip["ref_audio"], media_type="audio/wav")


@router.delete("/v1/voices/{voice_id}/emotions/{emotion}", tags=["Emotions"])
def delete_voice_emotion(voice_id: str, emotion: str):
    if not V.delete_emotion(voice_id, emotion):
        raise HTTPException(404, {"status": "not_found", "message": "No clip for this emotion"})
    return {"status": "ok"}


@router.post("/v1/voices/import-pack", tags=["Emotions"])
def import_emotion_pack(file: UploadFile = File(...), language: str = Form("")):
    """Import a .zip of ``<voice>_<emotion>.mp3`` clips (+ optional transcripts.txt, one
    ``file<TAB>exact words`` per line). Each voice is created (or updated) with its emotions."""
    import tempfile
    import zipfile

    (path,) = save_uploads([file], db.new_id("pack_"))
    with tempfile.TemporaryDirectory() as tmp, errors():
        try:
            with zipfile.ZipFile(path) as z:
                for member in z.infolist():
                    target = (Path(tmp) / member.filename).resolve()
                    if Path(tmp).resolve() not in target.parents or member.is_dir():
                        continue  # skip directories and unsafe paths
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(member))
        except zipfile.BadZipFile as exc:
            raise ValueError("The file is not a valid .zip") from exc
        result = V.import_pack(Path(tmp), language)
    return {"voices": result}


class DesignRequest(BaseModel):
    voice_description: str
    text: str | None = None
    language: str | None = None
    seed: int | None = None
    auto_generate_text: bool = False


SAMPLE_TEXT = ("Every voice tells a story. Mine began in a small town by the river, where the evenings were "
               "long and full of songs, laughter and the smell of rain.")


@router.get("/v1/text-to-voice/options", tags=["Voice design"])
def design_options():
    """The attributes the voice-design engine understands."""
    from ..voice_design import OPTIONS

    return {"options": OPTIONS, "example": "female, elderly, low pitch, british accent"}


@router.post("/v1/text-to-voice/create-previews", tags=["Voice design"])
@router.post("/v1/text-to-voice/design", tags=["Voice design"])
def design_voice(body: DesignRequest):
    text = body.text if body.text and not body.auto_generate_text else SAMPLE_TEXT
    with errors():
        previews = V.design_previews(body.voice_description, text, body.language, seed=body.seed)
    for p in previews:
        row = db.get("history", p["generated_voice_id"])
        p["audio_base_64"] = base64.b64encode(Path(row["audio"]).read_bytes()).decode()
        p["media_type"] = "audio/wav"
    return {"previews": previews, "text": text}


class SaveDesignRequest(BaseModel):
    voice_name: str
    generated_voice_id: str
    voice_description: str = ""
    labels: dict[str, str] | None = None


@router.post("/v1/text-to-voice/create-voice-from-preview", tags=["Voice design"])
@router.post("/v1/text-to-voice", tags=["Voice design"])
def save_designed_voice(body: SaveDesignRequest):
    with errors():
        v = V.save_designed(body.generated_voice_id, body.voice_name, body.voice_description, body.labels)
    return V.to_api(v)


# =============================================================== speech to text
@router.post("/v1/speech-to-text", tags=["Speech to text"])
def speech_to_text(file: UploadFile = File(...), model_id: str = Form("whisper"),
                   language_code: str | None = Form(None), diarize: bool = Form(False),
                   num_speakers: int | None = Form(None), format: str = Query("json")):
    (path,) = save_uploads([file], db.new_id("stt_"))
    with errors():
        tr = stt.transcribe(path, language_code or None, diarize, num_speakers)
    data = stt.to_api(tr)
    db.insert("history", {"id": db.new_id("h_"), "kind": "stt", "text": tr.text, "settings": {"segments":
              data["segments"], "language": tr.language}, "characters": len(tr.text), "created_at": db.now(),
              "voice_name": file.filename})
    if format == "srt":
        return PlainTextResponse(stt.to_srt(data["segments"], speakers=diarize), media_type="application/x-subrip")
    if format in ("vtt", "webvtt"):
        return PlainTextResponse(stt.to_vtt(data["segments"]), media_type="text/vtt")
    if format == "txt":
        return PlainTextResponse(tr.text)
    return data


# =============================================================== speech to speech (voice changer)
def _voice_changer(voice_id: str, audio: UploadFile, model_id: str, voice_settings: str | None,
                   remove_background_noise: bool, keep_background: bool, seed: int | None, output_format: str):
    (path,) = save_uploads([audio], db.new_id("sts_"))
    settings = parse_json_field(voice_settings, "voice_settings")
    with errors():
        out, sr, text = changer.convert(path, voice_id, settings, model_id, remove_background_noise,
                                        keep_background, seed=seed)
        voice = T.resolve_voice(voice_id)
        hid = T.save_history("sts", out, sr, text=text, voice=voice, settings={"voice_settings": settings})
    return audio_response(out, sr, output_format, hid, "voice_changed")


@router.post("/v1/speech-to-speech/{voice_id}", tags=["Voice changer"])
@router.post("/v1/speech-to-speech/{voice_id}/stream", tags=["Voice changer"])
def speech_to_speech(voice_id: str, audio: UploadFile = File(...), model_id: str = Form("kontho_v1"),
                     voice_settings: str | None = Form(None), remove_background_noise: bool = Form(False),
                     keep_background: bool = Form(False), seed: int | None = Form(None),
                     output_format: str = Query("mp3_44100_128")):
    return _voice_changer(voice_id, audio, model_id, voice_settings, remove_background_noise, keep_background,
                          seed, output_format)


# =============================================================== sound effects
class SFXRequest(BaseModel):
    text: str
    duration_seconds: float | None = Field(None, ge=0.5, le=30)
    prompt_influence: float = Field(0.3, ge=0, le=1)
    seed: int | None = None


@router.post("/v1/sound-generation", tags=["Sound effects"])
def sound_generation(body: SFXRequest, output_format: str = Query("mp3_44100_128")):
    with errors():
        audio, sr = sfx.generate(body.text, body.duration_seconds, body.prompt_influence, body.seed)
        hid = T.save_history("sfx", audio, sr, text=body.text, settings=body.model_dump())
    return audio_response(audio, sr, output_format, hid, "sound_effect")


# =============================================================== audio isolation
@router.post("/v1/audio-isolation", tags=["Voice isolator"])
@router.post("/v1/audio-isolation/stream", tags=["Voice isolator"])
def audio_isolation(audio: UploadFile = File(...), stem: str = Query("vocals", pattern="^(vocals|background)$"),
                    output_format: str = Query("mp3_44100_128")):
    (path,) = save_uploads([audio], db.new_id("iso_"))
    with errors():
        vocals, background, sr = sfx.isolate(path)
        out = vocals if stem == "vocals" else background
        hid = T.save_history("isolation", out, sr, text=audio.filename or "", settings={"stem": stem})
    return audio_response(out, sr, output_format, hid, stem)


# =============================================================== dubbing
@router.post("/v1/dubbing", tags=["Dubbing"])
def create_dubbing(file: UploadFile = File(...), target_lang: str = Form(...), source_lang: str = Form("auto"),
                   name: str = Form(""), num_speakers: int = Form(0), voice_id: str | None = Form(None),
                   drop_background_audio: bool = Form(False)):
    (path,) = save_uploads([file], db.new_id("dubsrc_"))
    with errors():
        job = dubbing.create(path, name or (file.filename or "Untitled"), target_lang,
                             None if source_lang in ("", "auto") else source_lang, num_speakers,
                             voice_id or None, not drop_background_audio)
    return {"dubbing_id": job["id"], "expected_duration_sec": round((job["input"]["duration"] or 0) * 3, 1)}


@router.get("/v1/dubbing", tags=["Dubbing"])
def list_dubbings():
    rows = db.query("SELECT * FROM jobs WHERE kind = 'dubbing' ORDER BY created_at DESC LIMIT 200")
    return {"dubs": [dubbing.to_api(j) for j in rows], "has_more": False}


def _dub(dubbing_id: str) -> dict:
    job = db.get("jobs", dubbing_id)
    if not job or job["kind"] != "dubbing":
        raise HTTPException(404, {"status": "dubbing_not_found", "message": "Dubbing project not found"})
    return job


@router.get("/v1/dubbing/{dubbing_id}", tags=["Dubbing"])
def get_dubbing(dubbing_id: str):
    return dubbing.to_api(_dub(dubbing_id))


@router.delete("/v1/dubbing/{dubbing_id}", tags=["Dubbing"])
def delete_dubbing(dubbing_id: str):
    _dub(dubbing_id)
    dubbing.delete(dubbing_id)
    return {"status": "ok"}


@router.get("/v1/dubbing/{dubbing_id}/audio/{language_code}", tags=["Dubbing"])
def dubbed_file(dubbing_id: str, language_code: str, kind: str = Query("auto", pattern="^(auto|audio)$")):
    _dub(dubbing_id)
    path = dubbing.output_file(dubbing_id, language_code, prefer_video=kind == "auto")
    if not path:
        raise HTTPException(425, {"status": "not_ready", "message": "Dubbing is not finished yet"})
    media = {".mp4": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}[path.suffix]
    return FileResponse(path, media_type=media, filename=f"dubbed_{language_code}{path.suffix}")


@router.get("/v1/dubbing/{dubbing_id}/transcript/{language_code}", tags=["Dubbing"])
def dubbed_transcript(dubbing_id: str, language_code: str, format_type: str = Query("srt")):
    _dub(dubbing_id)
    media = "text/vtt" if format_type in ("vtt", "webvtt") else "application/x-subrip"
    return PlainTextResponse(dubbing.subtitles(dubbing_id, language_code, format_type), media_type=media)


@router.get("/v1/dubbing/{dubbing_id}/source", tags=["Dubbing"])
def dubbing_source(dubbing_id: str):
    job = _dub(dubbing_id)
    return FileResponse(job["input"]["source"])


@router.get("/v1/dubbing/{dubbing_id}/segments", tags=["Dubbing studio"])
def dubbing_segments(dubbing_id: str):
    _dub(dubbing_id)
    state = dubbing.load_state(dubbing_id)
    return {"segments": state.get("segments", []), "speakers": list(state.get("speakers", {})),
            "source_lang": state.get("source_lang"), "target_lang": state.get("target_lang")}


class SegmentUpdate(BaseModel):
    text: str | None = None
    translation: str | None = None
    start: float | None = None
    end: float | None = None
    speaker: str | None = None
    voice_id: str | None = None
    retranslate: bool = False


@router.patch("/v1/dubbing/{dubbing_id}/segments/{index}", tags=["Dubbing studio"])
def update_dubbing_segment(dubbing_id: str, index: int, body: SegmentUpdate):
    _dub(dubbing_id)
    with errors():
        return dubbing.update_segment(dubbing_id, index, body.model_dump())


@router.post("/v1/dubbing/{dubbing_id}/render", tags=["Dubbing studio"])
def rerender_dubbing(dubbing_id: str):
    job = _dub(dubbing_id)
    if job["status"] in ("queued", "running"):
        raise HTTPException(409, {"status": "busy", "message": "Dubbing is still processing"})
    dubbing.rerender(dubbing_id)
    return {"status": "ok"}


# =============================================================== history
def _history_api(h: dict) -> dict:
    return {"history_item_id": h["id"], "kind": h["kind"], "voice_id": h.get("voice_id"),
            "voice_name": h.get("voice_name"), "text": h.get("text"), "settings": h.get("settings"),
            "character_count_change_from": 0, "character_count_change_to": h.get("characters") or 0,
            "date_unix": int(h["created_at"]), "content_type": h.get("content_type"),
            "has_audio": bool(h.get("audio")), "audio_url": f"/v1/history/{h['id']}/audio" if h.get("audio") else None}


@router.get("/v1/history", tags=["History"])
def list_history(page_size: int = Query(100, le=1000), start_after_history_item_id: str | None = None,
                 kind: str | None = None, voice_id: str | None = None):
    sql, params = "SELECT * FROM history WHERE kind != 'design'", []
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    if voice_id:
        sql += " AND voice_id = ?"
        params.append(voice_id)
    if start_after_history_item_id:
        ref = db.get("history", start_after_history_item_id)
        if ref:
            sql += " AND created_at < ?"
            params.append(ref["created_at"])
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(page_size + 1)
    rows = db.query(sql, params)
    items = [_history_api(h) for h in rows[:page_size]]
    return {"history": items, "has_more": len(rows) > page_size,
            "last_history_item_id": items[-1]["history_item_id"] if items else None}


@router.get("/v1/history/{history_item_id}", tags=["History"])
def get_history(history_item_id: str):
    h = db.get("history", history_item_id)
    if not h:
        raise HTTPException(404, {"status": "not_found", "message": "History item not found"})
    return _history_api(h)


@router.get("/v1/history/{history_item_id}/audio", tags=["History"])
def history_audio(history_item_id: str, output_format: str | None = None):
    h = db.get("history", history_item_id)
    if not h or not h.get("audio") or not Path(h["audio"]).exists():
        raise HTTPException(404, {"status": "not_found", "message": "Audio not found"})
    if output_format:
        audio, sr = A.load_audio(h["audio"], sr=None)
        return audio_response(audio, sr, output_format, None, h["id"])
    return FileResponse(h["audio"], media_type=h.get("content_type") or "audio/wav")


@router.delete("/v1/history/{history_item_id}", tags=["History"])
def delete_history(history_item_id: str):
    h = db.get("history", history_item_id)
    if not h:
        raise HTTPException(404, {"status": "not_found", "message": "History item not found"})
    if h.get("audio"):
        Path(h["audio"]).unlink(missing_ok=True)
    db.delete("history", history_item_id)
    return {"status": "ok"}


# =============================================================== pronunciation dictionary
class PronunciationRule(BaseModel):
    term: str
    replacement: str
    language: str = ""


@router.get("/v1/pronunciation", tags=["Pronunciation"])
def list_pronunciation():
    return {"rules": db.query("SELECT * FROM pronunciation ORDER BY term")}


@router.post("/v1/pronunciation", tags=["Pronunciation"])
def add_pronunciation(rule: PronunciationRule):
    row = {"id": db.new_id("pr_"), **rule.model_dump(), "created_at": db.now()}
    db.insert("pronunciation", row)
    return row


@router.delete("/v1/pronunciation/{rule_id}", tags=["Pronunciation"])
def delete_pronunciation(rule_id: str):
    if not db.delete("pronunciation", rule_id):
        raise HTTPException(404, {"status": "not_found", "message": "Rule not found"})
    return {"status": "ok"}


# =============================================================== account, models, system
@router.get("/v1/models", tags=["Models"])
def models():
    return [{**{k: v for k, v in m.items() if k != "steps"}, "languages": language_list()} for m in T.MODELS]


@router.get("/v1/languages", tags=["Models"])
def languages():
    return {"languages": language_list()}


@router.get("/v1/user", tags=["User"])
def user():
    return {"user_id": "local", "subscription": user_subscription(), "is_new_user": False,
            "xi_api_key": None, "first_name": "Self-hosted"}


@router.get("/v1/user/subscription", tags=["User"])
def user_subscription():
    used = db.query("SELECT COALESCE(SUM(characters), 0) AS n FROM history WHERE kind IN ('tts', 'sts')")[0]["n"]
    return {"tier": "self_hosted", "character_count": used, "character_limit": 10**12,
            "can_extend_character_limit": False, "voice_limit": 10**6, "status": "active",
            "can_use_instant_voice_cloning": True, "can_use_professional_voice_cloning": False}


@router.get("/v1/system/status", tags=["System"])
def system_status():
    shutil_ok = bool(shutil.which(A.FFMPEG))
    return {"version": __version__, "ffmpeg": shutil_ok, "engines": E.status(),
            "device": __import__("kontho.config", fromlist=["x"]).get_settings().resolved_device()}


class KeyRequest(BaseModel):
    name: str = "API key"


@router.get("/v1/api-keys", tags=["API keys"])
def list_keys():
    return {"keys": db.query("SELECT id, name, prefix, created_at, last_used_at FROM api_keys ORDER BY created_at DESC")}


@router.post("/v1/api-keys", tags=["API keys"])
def create_key(body: KeyRequest):
    raw, row = new_api_key(body.name)
    return {"id": row["id"], "name": row["name"], "api_key": raw,
            "note": "Store this key now; it cannot be shown again."}


@router.delete("/v1/api-keys/{key_id}", tags=["API keys"])
def delete_key(key_id: str):
    if not db.delete("api_keys", key_id):
        raise HTTPException(404, {"status": "not_found", "message": "Key not found"})
    return {"status": "ok"}


