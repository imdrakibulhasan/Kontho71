import io
import zipfile

from kontho import audio as A
from kontho import emotions as E


def test_parse_tags():
    runs = E.parse("Hello. [angry] খবরদার! [laughter] হা হা [calm] শান্ত হও। [neutral] Bye")
    assert runs == [(None, "Hello."), ("angry", "খবরদার! [laughter] হা হা"), ("calm", "শান্ত হও।"), (None, "Bye")]
    # ElevenLabs-style multi-word tags: last recognised emotion wins; unknown tags dropped; [pause] kept as a pause
    assert E.parse("[warm, smooth, gentle storytelling tone, tense] বাঁধ ভেঙে গেছে। [pause] পানি ঢুকছে।") == [
        ("tense", "বাঁধ ভেঙে গেছে। … পানি ঢুকছে।")]
    assert E.parse("[young man, surprised, doubtful, rural accent] কী হইব?") == [("surprised", "কী হইব?")]
    assert E.parse("[screaming, panicked, desperate] বাঁচান!")[0][0] == "scared"
    assert E.parse("[rural accent] text") == [(None, "text")]
    assert E.parse("plain", default="sad") == [("sad", "plain")]


def test_resolve_fallbacks():
    assert E.resolve("shouting", {"angry"}) == "angry"
    assert E.resolve("crying", {"sad", "angry"}) == "sad"
    assert E.resolve("whisper", {"angry"}) is None


def _clip(tmp_path, name, freq=200, dur=4.0):
    p = tmp_path / name
    import numpy as np
    t = np.arange(int(dur * 24000)) / 24000
    A.save_wav(p, (0.3 * np.sin(2 * np.pi * freq * t)).astype("float32"), 24000)
    return p


def test_voice_emotions_and_tagged_tts(client, tmp_path):
    with _clip(tmp_path, "base.wav").open("rb") as f:
        vid = client.post("/v1/voices/add", data={"name": "Emo"}, files=[("files", ("b.wav", f, "audio/wav"))]).json()["voice_id"]
    for emo, freq in (("angry", 300), ("annoyed", 310), ("sad", 150)):
        with _clip(tmp_path, f"{emo}.wav", freq).open("rb") as f:
            r = client.post(f"/v1/voices/{vid}/emotions", data={"emotion": emo, "reference_text": "words"},
                            files=[("files", ("x.wav", f, "audio/wav"))])
        assert r.status_code == 200, r.text
    assert client.post(f"/v1/voices/{vid}/emotions", data={"emotion": "bogus"},
                       files=[("files", ("x.wav", b"x", "audio/wav"))]).status_code == 422
    emos = client.get(f"/v1/voices/{vid}/emotions").json()["emotions"]
    assert {e["emotion"] for e in emos} == {"angry", "sad"}  # "annoyed" is an alias of angry (replaced)
    assert client.get(f"/v1/voices/{vid}").json()["emotions"] == ["angry", "sad"]
    assert client.get(emos[0]["audio_url"]).status_code == 200

    r = client.post(f"/v1/text-to-speech/{vid}",
                    json={"text": "Hello [shouting] stop it! [crying] please. [whisper] psst"})
    assert r.status_code == 200
    assert r.headers["emotions-used"] == "shouting=angry,crying=sad,whisper=base"
    r = client.post(f"/v1/text-to-speech/{vid}", json={"text": "all sad", "emotion": "sad"})
    assert r.headers["emotions-used"] == "sad=sad"

    assert client.delete(f"/v1/voices/{vid}/emotions/sad").status_code == 200
    assert client.get(f"/v1/voices/{vid}").json()["emotions"] == ["angry"]
    assert client.get("/v1/emotions").json()["emotions"][0]["emotion"] == "neutral"


def test_import_pack(client, tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, freq in (("narrator_neutral", 200), ("narrator_neutral2", 210), ("narrator_sad", 150),
                           ("narrator_tense", 250), ("rahima_angry", 300), ("rahima_crying", 320),
                           ("readme_x", 100)):
            z.write(_clip(tmp_path, f"{name}.wav", freq, dur=3 + freq / 1000), f"pack/{name}.mp3")
        z.writestr("pack/transcripts.txt", "narrator_sad.mp3\t[sad] দুঃখের কথা।\nrahima_angry.mp3: রাগের কথা!\n")
        z.writestr("../evil.mp3", b"nope")
    buf.seek(0)
    r = client.post("/v1/voices/import-pack", files={"file": ("pack.zip", buf, "application/zip")})
    assert r.status_code == 200, r.text
    voices = {v["name"]: v for v in r.json()["voices"]}
    assert voices["Narrator"]["base"] == "neutral" and voices["Narrator"]["emotions"] == ["sad", "tense"]
    assert voices["Rahima"]["base"] == "crying" and voices["Rahima"]["emotions"] == ["angry", "crying"]
    nid = voices["Narrator"]["voice_id"]
    sad = [e for e in client.get(f"/v1/voices/{nid}/emotions").json()["emotions"] if e["emotion"] == "sad"][0]
    assert sad["reference_text"] == "দুঃখের কথা।"
    # re-importing updates the same voices
    buf.seek(0)
    again = client.post("/v1/voices/import-pack", files={"file": ("pack.zip", buf, "application/zip")}).json()
    assert {v["voice_id"] for v in again["voices"]} == {v["voice_id"] for v in voices.values()}
    bad = client.post("/v1/voices/import-pack", files={"file": ("x.zip", b"not a zip", "application/zip")})
    assert bad.status_code == 422
