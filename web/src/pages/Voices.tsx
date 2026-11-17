import { useEffect, useMemo, useState } from "react";
import { del, getJSON, postForm, sendJSON, Voice } from "../api";
import { refreshVoices, useEmotionCatalog, useObjectUrls, useVoices } from "../hooks";
import { AudioPlayer, Empty, ErrorBox, FileDrop, LanguageSelect, Modal, PageHeader, Recorder, Spinner } from "../components/ui";
import { PreviewButton, VoiceAvatar } from "../components/VoicePicker";

const TABS = ["all", "cloned", "designed", "premade"] as const;

export default function Voices() {
  const { voices, loading, error } = useVoices();
  const [tab, setTab] = useState<(typeof TABS)[number]>("all");
  const [q, setQ] = useState("");
  const [modal, setModal] = useState<"clone" | "design" | "pack" | null>(null);
  const [editing, setEditing] = useState<Voice | null>(null);
  const shown = useMemo(
    () => voices.filter((v) => (tab === "all" || v.category === tab) && v.name.toLowerCase().includes(q.toLowerCase())),
    [voices, tab, q],
  );
  return (
    <>
      <PageHeader
        title="Voices"
        subtitle="Clone your voice from a short sample, design new voices from a description, or use premade ones."
        actions={
          <>
            <button className="btn ghost" onClick={() => setModal("pack")}>⇪ Import emotion pack</button>
            <button className="btn ghost" onClick={() => setModal("design")}>✦ Design a voice</button>
            <button className="btn primary" onClick={() => setModal("clone")}>+ Clone a voice</button>
          </>
        }
      />
      <div className="row between wrap gap mb">
        <div className="tabs">
          {TABS.map((t) => (
            <button key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <input className="search" placeholder="Search voices…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <ErrorBox error={error} />
      {loading && !voices.length ? (
        <Spinner label="Loading voices" />
      ) : shown.length === 0 ? (
        <Empty title="No voices here yet">Clone or design one to get started.</Empty>
      ) : (
        <div className="grid">
          {shown.map((v) => (
            <div key={v.voice_id} className="card voice-card">
              <div className="row gap">
                <VoiceAvatar voice={v} />
                <div className="grow">
                  <strong>{v.name}</strong>
                  <div className="muted small">{v.category}{v.language ? ` · ${v.language}` : ""}</div>
                </div>
                <PreviewButton voice={v} />
              </div>
              {v.description && <p className="small muted clamp">{v.description}</p>}
              <div className="row gap wrap">
                {v.emotions.length > 0 && <span className="tag emo-tag" title={v.emotions.join(", ")}>{v.emotions.length} emotion{v.emotions.length > 1 ? "s" : ""}</span>}
                {Object.entries(v.labels).map(([k, val]) => (
                  <span key={k} className="tag">{val}</span>
                ))}
              </div>
              <div className="row gap">
                <code className="small muted grow ellipsis" title="Voice ID">{v.voice_id}</code>
                {v.category !== "premade" && (
                  <button className="btn ghost small" onClick={() => setEditing(v)}>Edit</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {modal === "clone" && <CloneModal onClose={() => setModal(null)} />}
      {modal === "design" && <DesignModal onClose={() => setModal(null)} />}
      {modal === "pack" && <PackModal onClose={() => setModal(null)} />}
      {editing && <EditModal voice={editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function CloneModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [desc, setDesc] = useState("");
  const [refText, setRefText] = useState("");
  const [lang, setLang] = useState("");
  const [gender, setGender] = useState("");
  const [accent, setAccent] = useState("");
  const [denoise, setDenoise] = useState(false);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    const f = new FormData();
    f.append("name", name);
    files.forEach((x) => f.append("files", x));
    f.append("description", desc);
    f.append("language", lang);
    f.append("remove_background_noise", String(denoise));
    if (refText.trim()) f.append("reference_text", refText.trim());
    const labels: Record<string, string> = {};
    if (gender) labels.gender = gender;
    if (accent) labels.accent = accent;
    f.append("labels", JSON.stringify(labels));
    try {
      await postForm("/v1/voices/add", f);
      refreshVoices();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title="Instant voice clone" onClose={onClose}>
      <p className="muted small">Upload or record 10–30 seconds of clean speech from a single speaker. Longer samples are trimmed to the best 15 seconds.</p>
      <div className="field"><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. My narrator" /></div>
      <FileDrop accept="audio/*,video/*" multiple files={files} onFiles={setFiles} hint="MP3, WAV, M4A, OGG, MP4… up to 500 MB" />
      <Recorder onRecorded={(f) => setFiles((x) => [...x, f])} />
      <div className="field">
        <label>Exact words spoken in the sample <span className="muted">(optional, auto-transcribed if empty)</span></label>
        <textarea rows={2} value={refText} onChange={(e) => setRefText(e.target.value)} />
      </div>
      <div className="row gap wrap">
        <div className="field grow"><label>Language</label><LanguageSelect value={lang} onChange={setLang} allowAuto /></div>
        <div className="field grow">
          <label>Gender</label>
          <select value={gender} onChange={(e) => setGender(e.target.value)}>
            <option value="">—</option><option value="female">Female</option><option value="male">Male</option><option value="neutral">Neutral</option>
          </select>
        </div>
        <div className="field grow"><label>Accent</label><input value={accent} onChange={(e) => setAccent(e.target.value)} placeholder="e.g. Dhaka" /></div>
      </div>
      <div className="field"><label>Description</label><input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Warm, calm storyteller" /></div>
      <label className="check"><input type="checkbox" checked={denoise} onChange={(e) => setDenoise(e.target.checked)} /> Remove background noise from the samples</label>
      <label className="check"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> I have the right and the consent of the speaker to clone this voice, and I won't use it to deceive or harm anyone.</label>
      <ErrorBox error={error} />
      <div className="row end gap">
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className="btn primary" disabled={busy || !name || !files.length || !consent} onClick={submit}>
          {busy ? <Spinner label="Cloning" /> : "Add voice"}
        </button>
      </div>
    </Modal>
  );
}

type Preview = { generated_voice_id: string; audio_base_64: string; duration_secs: number };

type DesignOptions = Record<"gender" | "age" | "pitch" | "accent" | "style", string[]>;

function DesignModal({ onClose }: { onClose: () => void }) {
  const [opts, setOpts] = useState<DesignOptions | null>(null);
  const [attrs, setAttrs] = useState<Record<string, string>>({ gender: "female", age: "young adult", pitch: "moderate pitch", accent: "", style: "" });
  const desc = ["gender", "age", "pitch", "accent", "style"].map((k) => attrs[k]).filter(Boolean).join(", ");
  useEffect(() => {
    getJSON<{ options: DesignOptions }>("/v1/text-to-voice/options").then((r) => setOpts(r.options)).catch(() => {});
  }, []);
  const [text, setText] = useState("");
  const [lang, setLang] = useState("en");
  const [previews, setPreviews] = useState<{ p: Preview; url: string }[]>([]);
  const [chosen, setChosen] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toUrl = useObjectUrls();
  const generate = async () => {
    setBusy(true);
    setError(null);
    setChosen(null);
    try {
      const r = await sendJSON<{ previews: Preview[] }>("/v1/text-to-voice/create-previews", {
        voice_description: desc, text: text.trim() || null, auto_generate_text: !text.trim(), language: lang || null,
      });
      setPreviews(r.previews.map((p) => {
        const bytes = Uint8Array.from(atob(p.audio_base_64), (c) => c.charCodeAt(0));
        return { p, url: toUrl(new Blob([bytes], { type: "audio/wav" })) };
      }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    setBusy(true);
    try {
      await sendJSON("/v1/text-to-voice/create-voice-from-preview", { voice_name: name, generated_voice_id: chosen, voice_description: desc });
      refreshVoices();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title="Design a voice" onClose={onClose} wide>
      <p className="muted small">Pick the voice's attributes. Each set of previews is a new random voice matching them.</p>
      <div className="row gap wrap">
        {opts && (["gender", "age", "pitch", "accent", "style"] as const).map((k) => (
          <div key={k} className="field grow">
            <label>{k === "style" ? "Style" : k[0].toUpperCase() + k.slice(1)}</label>
            <select value={attrs[k]} onChange={(e) => setAttrs({ ...attrs, [k]: e.target.value })}>
              <option value="">{k === "accent" ? "Neutral" : k === "style" ? "Normal" : "Any"}</option>
              {opts[k].map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
        ))}
      </div>
      <div className="muted small">Prompt: <code>{desc || "—"}</code></div>
      <div className="row gap wrap">
        <div className="field grow"><label>Preview text <span className="muted">(optional)</span></label><input value={text} onChange={(e) => setText(e.target.value)} placeholder="Leave empty for a sample sentence" /></div>
        <div className="field"><label>Language</label><LanguageSelect value={lang} onChange={setLang} /></div>
      </div>
      <p className="muted small">For Bengali and other accents that must be exact, cloning a real reference sample gives the most consistent result.</p>
      <div className="row end"><button className="btn primary" disabled={busy || !desc.trim()} onClick={generate}>{busy && !previews.length ? <Spinner label="Generating 3 previews" /> : "Generate previews"}</button></div>
      {previews.length > 0 && (
        <div className="stack">
          {previews.map(({ p, url }, i) => (
            <label key={p.generated_voice_id} className={`preview-row ${chosen === p.generated_voice_id ? "active" : ""}`}>
              <input type="radio" name="pick" checked={chosen === p.generated_voice_id} onChange={() => setChosen(p.generated_voice_id)} />
              <span>Option {i + 1}</span>
              <AudioPlayer src={url} />
            </label>
          ))}
          <div className="row gap">
            <input className="grow" placeholder="Name your voice" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn primary" disabled={!chosen || !name || busy} onClick={save}>Save voice</button>
          </div>
        </div>
      )}
      <ErrorBox error={error} />
    </Modal>
  );
}

function EditModal({ voice, onClose }: { voice: Voice; onClose: () => void }) {
  const [name, setName] = useState(voice.name);
  const [desc, setDesc] = useState(voice.description);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    const f = new FormData();
    f.append("name", name);
    f.append("description", desc);
    try {
      await postForm(`/v1/voices/${voice.voice_id}/edit`, f);
      refreshVoices();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const remove = async () => {
    if (!confirm(`Delete the voice "${voice.name}"? This cannot be undone.`)) return;
    try {
      await del(`/v1/voices/${voice.voice_id}`);
      refreshVoices();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <Modal title={`Edit ${voice.name}`} onClose={onClose} wide>
      <div className="field"><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
      <div className="field"><label>Description</label><textarea rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} /></div>
      <AudioPlayer src={voice.preview_url} title="Normal reference sample" />
      <EmotionManager voice={voice} />
      <ErrorBox error={error} />
      <div className="row between">
        <button className="btn danger" onClick={remove}>Delete voice</button>
        <button className="btn primary" onClick={save}>Save</button>
      </div>
    </Modal>
  );
}


type EmotionClip = { emotion: string; reference_text: string | null; audio_url: string };

function EmotionManager({ voice }: { voice: Voice }) {
  const catalog = useEmotionCatalog();
  const [clips, setClips] = useState<EmotionClip[]>([]);
  const [emotion, setEmotion] = useState("angry");
  const [files, setFiles] = useState<File[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const load = () => getJSON<{ emotions: EmotionClip[] }>(`/v1/voices/${voice.voice_id}/emotions`).then((r) => setClips(r.emotions)).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [voice.voice_id]); // eslint-disable-line react-hooks/exhaustive-deps
  const add = async () => {
    setBusy(true);
    setError(null);
    const f = new FormData();
    f.append("emotion", emotion);
    files.forEach((x) => f.append("files", x));
    if (text.trim()) f.append("reference_text", text.trim());
    try {
      await postForm(`/v1/voices/${voice.voice_id}/emotions`, f);
      setFiles([]);
      setText("");
      setVersion((v) => v + 1);
      load();
      refreshVoices();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const name = (e: string) => catalog.find((c) => c.emotion === e);
  return (
    <div className="stack emotion-manager">
      <h3>Emotions</h3>
      <p className="muted small">
        Give this voice one 5–10 s clip per emotion. Write <code>[angry]</code>, <code>[sad]</code>… in your text and that part is spoken
        with the matching clip's emotion. Missing emotions fall back to a related one, then to the normal voice.
      </p>
      {clips.length === 0 && <div className="muted small">No emotion clips yet.</div>}
      {clips.map((c) => (
        <div key={c.emotion} className="emotion-row">
          <div className="emotion-name">
            <strong>{name(c.emotion)?.name || c.emotion}</strong> <span className="muted small">{name(c.emotion)?.name_bn}</span>
            {c.reference_text && <div className="muted small clamp">{c.reference_text}</div>}
          </div>
          <AudioPlayer src={`${c.audio_url}?v=${version}`} />
          <button className="icon-btn" title="Remove" onClick={async () => { await del(`/v1/voices/${voice.voice_id}/emotions/${c.emotion}`); load(); refreshVoices(); }}>🗑</button>
        </div>
      ))}
      <div className="card inset">
        <div className="row gap wrap">
          <div className="field">
            <label>Emotion</label>
            <select value={emotion} onChange={(e) => setEmotion(e.target.value)}>
              {catalog.filter((c) => c.emotion !== "neutral").map((c) => (
                <option key={c.emotion} value={c.emotion}>{c.name} · {c.name_bn}{clips.some((x) => x.emotion === c.emotion) ? " ✓" : ""}</option>
              ))}
            </select>
          </div>
          <div className="field grow"><label>Exact words in the clip <span className="muted">(optional)</span></label><input value={text} onChange={(e) => setText(e.target.value)} /></div>
        </div>
        <FileDrop accept="audio/*,video/*" files={files} onFiles={setFiles} hint="A clip spoken with this emotion" />
        <div className="row between wrap gap">
          <Recorder onRecorded={(f) => setFiles([f])} />
          <button className="btn primary" disabled={!files.length || busy} onClick={add}>{busy ? <Spinner label="Adding" /> : "Add emotion clip"}</button>
        </div>
        <ErrorBox error={error} onClose={() => setError(null)} />
      </div>
    </div>
  );
}

function PackModal({ onClose }: { onClose: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [lang, setLang] = useState("bn");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ name: string; base: string; emotions: string[] }[] | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    const f = new FormData();
    f.append("file", files[0]);
    f.append("language", lang);
    try {
      const r = await postForm<{ voices: { name: string; base: string; emotions: string[] }[] }>("/v1/voices/import-pack", f);
      setResult(r.voices);
      refreshVoices();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title="Import emotion pack" onClose={onClose}>
      <p className="muted small">
        A .zip of clips named <code>voice_emotion.mp3</code> (e.g. <code>narrator_calm.mp3</code>, <code>rahima_angry.mp3</code>) and an
        optional <code>transcripts.txt</code> with one <code>file⇥exact words</code> per line. Each voice is created, or updated if it
        already exists, with all its emotions.
      </p>
      <FileDrop accept=".zip,application/zip" files={files} onFiles={setFiles} hint="voice_emotion_pack.zip" />
      <div className="field"><label>Language of the clips</label><LanguageSelect value={lang} onChange={setLang} allowAuto /></div>
      <ErrorBox error={error} />
      {result && (
        <div className="notice">
          {result.map((v) => <div key={v.name}><strong>{v.name}</strong>: normal voice from “{v.base}”, emotions: {v.emotions.join(", ") || "none"}</div>)}
        </div>
      )}
      <div className="row end gap">
        <button className="btn ghost" onClick={onClose}>{result ? "Done" : "Cancel"}</button>
        {!result && <button className="btn primary" disabled={!files.length || busy} onClick={submit}>{busy ? <Spinner label="Importing" /> : "Import"}</button>}
      </div>
    </Modal>
  );
}
