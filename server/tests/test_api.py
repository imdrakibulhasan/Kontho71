import io

import soundfile as sf

from conftest import wait_job

from kontho import audio as A
from kontho.text import chunk_text, split_sentences


def test_health_and_status(client):
    assert client.get("/health").json()["status"] == "ok"
    st = client.get("/v1/system/status").json()
    assert st["engines"]["tts"]["engine"] == "mock"


def test_premade_voices(client):
    voices = client.get("/v1/voices").json()["voices"]
    assert len(voices) >= 8
    assert all({"voice_id", "name", "category", "preview_url"} <= v.keys() for v in voices)
    r = client.get(voices[0]["preview_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"


def test_tts_formats(client):
    for fmt, ctype in [("mp3_44100_128", "audio/mpeg"), ("wav_24000", "audio/wav"), ("pcm_16000", "audio/pcm"),
                       ("opus_48000_64", "audio/ogg")]:
        r = client.post(f"/v1/text-to-speech/premade_aria?output_format={fmt}",
                        json={"text": "Hello world. আমি বাংলায় কথা বলি। Bonjour !", "language_code": "bn"})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith(ctype)
        assert len(r.content) > 100
        assert r.headers["history-item-id"].startswith("h_")
    wav = client.post("/v1/text-to-speech/premade_aria?output_format=wav_16000", json={"text": "Testing"}).content
    data, sr = sf.read(io.BytesIO(wav))
    assert sr == 16000 and len(data) > 1000


def test_tts_errors(client):
    assert client.post("/v1/text-to-speech/nope", json={"text": "hi"}).status_code == 404
    assert client.post("/v1/text-to-speech/premade_aria", json={"text": "  "}).status_code == 422
    assert client.post("/v1/text-to-speech/premade_aria?output_format=xyz", json={"text": "a"}).status_code == 422


def test_tts_stream_and_timestamps(client):
    with client.stream("POST", "/v1/text-to-speech/premade_roger/stream?output_format=pcm_24000",
                       json={"text": "First sentence. Second sentence. Third one!"}) as r:
        chunks = [c for c in r.iter_bytes() if c]
    assert r.status_code == 200 and sum(map(len, chunks)) > 1000
    ts = client.post("/v1/text-to-speech/premade_roger/with-timestamps", json={"text": "Hi there. Bye."}).json()
    al = ts["alignment"]
    assert "".join(al["characters"]).startswith("Hi there.")
    assert al["character_end_times_seconds"][-1] > 0 and ts["audio_base64"]


def test_clone_edit_delete_voice(client, speech_wav):
    with speech_wav.open("rb") as f:
        r = client.post("/v1/voices/add", data={"name": "My voice", "labels": '{"accent": "dhaka"}'},
                        files=[("files", ("me.wav", f, "audio/wav"))])
    assert r.status_code == 200, r.text
    vid = r.json()["voice_id"]
    v = client.get(f"/v1/voices/{vid}").json()
    assert v["category"] == "cloned" and v["labels"]["accent"] == "dhaka"
    assert client.post(f"/v1/voices/{vid}/edit", data={"name": "Renamed"}).status_code == 200
    assert client.get(f"/v1/voices/{vid}").json()["name"] == "Renamed"
    assert client.post(f"/v1/text-to-speech/{vid}", json={"text": "cloned speech"}).status_code == 200
    assert client.delete(f"/v1/voices/{vid}").status_code == 200
    assert client.get(f"/v1/voices/{vid}").status_code == 404
    assert client.delete("/v1/voices/premade_aria").status_code == 404  # premade voices are protected


def test_clone_rejects_short_audio(client, tmp_path):
    p = tmp_path / "short.wav"
    A.save_wav(p, A.silence(0.5, 24000), 24000)
    with p.open("rb") as f:
        r = client.post("/v1/voices/add", data={"name": "x"}, files=[("files", ("s.wav", f, "audio/wav"))])
    assert r.status_code == 422


def test_voice_design(client):
    r = client.post("/v1/text-to-voice/create-previews",
                    json={"voice_description": "old wise man, deep", "text": "Once upon a time there lived a king."})
    previews = r.json()["previews"]
    assert len(previews) == 3 and previews[0]["audio_base_64"]
    saved = client.post("/v1/text-to-voice/create-voice-from-preview",
                        json={"voice_name": "Wise", "generated_voice_id": previews[1]["generated_voice_id"]}).json()
    assert saved["category"] == "designed"
    assert client.post(f"/v1/text-to-speech/{saved['voice_id']}", json={"text": "designed"}).status_code == 200


def test_speech_to_text(client, speech_wav):
    with speech_wav.open("rb") as f:
        r = client.post("/v1/speech-to-text", data={"diarize": "true", "num_speakers": "2"},
                        files={"file": ("a.wav", f, "audio/wav")})
    data = r.json()
    assert data["text"] and data["words"] and len(data["segments"]) >= 2
    assert {w["speaker_id"] for w in data["words"]} == {"speaker_0", "speaker_1"}
    with speech_wav.open("rb") as f:
        srt = client.post("/v1/speech-to-text?format=srt", files={"file": ("a.wav", f, "audio/wav")}).text
    assert "-->" in srt and srt.startswith("1\n")


def test_voice_changer(client, speech_wav):
    with speech_wav.open("rb") as f:
        r = client.post("/v1/speech-to-speech/premade_liam?output_format=wav_24000",
                        files={"audio": ("a.wav", f, "audio/wav")}, data={"remove_background_noise": "true"})
    assert r.status_code == 200, r.text
    data, sr = sf.read(io.BytesIO(r.content))
    assert abs(len(data) / sr - 6.0) < 0.6  # timing preserved


def test_sound_effects_and_isolation(client, speech_wav):
    r = client.post("/v1/sound-generation", json={"text": "thunder rolling over hills", "duration_seconds": 2})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert client.post("/v1/sound-generation", json={"text": "x", "duration_seconds": 99}).status_code == 422
    for stem in ("vocals", "background"):
        with speech_wav.open("rb") as f:
            r = client.post(f"/v1/audio-isolation?stem={stem}", files={"audio": ("a.wav", f, "audio/wav")})
        assert r.status_code == 200


def test_history(client):
    client.post("/v1/text-to-speech/premade_aria", json={"text": "for history"})
    h = client.get("/v1/history?page_size=2").json()
    assert len(h["history"]) == 2 and h["has_more"]
    item = h["history"][0]
    assert client.get(f"/v1/history/{item['history_item_id']}/audio").status_code == 200
    nxt = client.get(f"/v1/history?page_size=2&start_after_history_item_id={h['last_history_item_id']}").json()
    assert nxt["history"][0]["history_item_id"] not in {i["history_item_id"] for i in h["history"]}
    assert client.delete(f"/v1/history/{item['history_item_id']}").status_code == 200
    assert client.get(f"/v1/history/{item['history_item_id']}").status_code == 404


def test_dubbing_video_and_studio_edit(client, video_file):
    with video_file.open("rb") as f:
        r = client.post("/v1/dubbing", data={"target_lang": "bn", "source_lang": "en", "num_speakers": "2"},
                        files={"file": ("clip.mp4", f, "video/mp4")})
    assert r.status_code == 200, r.text
    dub_id = r.json()["dubbing_id"]
    d = wait_job(client, dub_id)
    assert d["status"] == "dubbed", d
    out = client.get(f"/v1/dubbing/{dub_id}/audio/bn")
    assert out.status_code == 200 and out.headers["content-type"] == "video/mp4"
    audio_only = client.get(f"/v1/dubbing/{dub_id}/audio/bn?kind=audio")
    assert audio_only.headers["content-type"] == "audio/mpeg"
    srt = client.get(f"/v1/dubbing/{dub_id}/transcript/bn").text
    assert "[bn]" in srt
    segs = client.get(f"/v1/dubbing/{dub_id}/segments").json()["segments"]
    assert segs and all(not s["dirty"] for s in segs)
    edited = client.patch(f"/v1/dubbing/{dub_id}/segments/0", json={"translation": "নতুন অনুবাদ"}).json()
    assert edited["dirty"] and edited["translation"] == "নতুন অনুবাদ"
    assert client.post(f"/v1/dubbing/{dub_id}/render").status_code == 200
    assert wait_job(client, dub_id)["status"] == "dubbed"
    assert "নতুন অনুবাদ" in client.get(f"/v1/dubbing/{dub_id}/transcript/bn").text
    assert any(x["dubbing_id"] == dub_id for x in client.get("/v1/dubbing").json()["dubs"])
    assert client.delete(f"/v1/dubbing/{dub_id}").status_code == 200
    assert client.get(f"/v1/dubbing/{dub_id}").status_code == 404


def test_pronunciation_dictionary(client):
    rule = client.post("/v1/pronunciation", json={"term": "AB", "replacement": "Amar Bangla"}).json()
    assert any(r["id"] == rule["id"] for r in client.get("/v1/pronunciation").json()["rules"])
    assert client.delete(f"/v1/pronunciation/{rule['id']}").status_code == 200


def test_models_user_languages(client):
    assert {m["model_id"] for m in client.get("/v1/models").json()} >= {"kontho_v1", "kontho_turbo"}
    assert client.get("/v1/user/subscription").json()["tier"] == "self_hosted"
    assert any(lang["language_id"] == "bn" for lang in client.get("/v1/languages").json()["languages"])


def test_text_utils():
    assert split_sentences("আমি ভাত খাই। তুমি কী খাও? Okay.") == ["আমি ভাত খাই।", "তুমি কী খাও?", "Okay."]
    chunks = chunk_text("word " * 400, max_chars=100)
    assert all(len(c) <= 100 for c in chunks) and len(chunks) > 5
    assert A.parse_output_format("mp3_22050_32").bitrate == 32
    assert A.parse_output_format("ulaw_8000").content_type == "audio/basic"


def test_voice_design_vocabulary(client):
    from kontho.voice_design import normalize

    assert normalize("Old man with a deep voice, British") == ("male, elderly, low pitch, british accent", [])
    instr, ignored = normalize("female, warm, cheerful, young")
    assert instr == "female, young adult" and ignored == ["warm", "cheerful"]
    assert client.get("/v1/text-to-voice/options").json()["options"]["gender"] == ["male", "female"]
    r = client.post("/v1/text-to-voice/create-previews", json={"voice_description": "warm and cheerful"})
    assert r.status_code == 422
