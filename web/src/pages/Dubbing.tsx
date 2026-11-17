import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { del, Dub, getJSON, postForm } from "../api";
import { Empty, ErrorBox, FileDrop, fmtDate, LanguageSelect, Modal, PageHeader, Spinner } from "../components/ui";
import { VoicePicker } from "../components/VoicePicker";

export function StatusPill({ d }: { d: Dub }) {
  if (d.status === "dubbing") return <span className="pill busy">{Math.round(d.progress * 100)}% · {d.message}</span>;
  if (d.status === "failed") return <span className="pill bad" title={d.error || ""}>Failed</span>;
  return <span className="pill ok">Ready</span>;
}

export default function Dubbing() {
  const [dubs, setDubs] = useState<Dub[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const load = () => getJSON<{ dubs: Dub[] }>("/v1/dubbing").then((r) => setDubs(r.dubs)).catch((e) => setError(e.message)).finally(() => setLoading(false));
  useEffect(() => {
    load();
    const t = window.setInterval(load, 3000);
    return () => window.clearInterval(t);
  }, []);
  return (
    <>
      <PageHeader
        title="Dubbing"
        subtitle="Translate video and audio into another language, in the original speakers' voices."
        actions={<button className="btn primary" onClick={() => setCreating(true)}>+ New dub</button>}
      />
      <ErrorBox error={error} />
      {loading ? <Spinner label="Loading" /> : dubs.length === 0 ? (
        <Empty title="No dubbing projects yet">Upload a video or audio file to dub it into Bengali, French, English or 35+ other languages.</Empty>
      ) : (
        <div className="table">
          {dubs.map((d) => (
            <Link key={d.dubbing_id} to={`/dubbing/${d.dubbing_id}`} className="table-row">
              <span className="grow ellipsis"><strong>{d.name}</strong></span>
              <span className="muted small">{d.source_language || "auto"} → {d.target_languages.join(", ")}</span>
              <span className="muted small hide-sm">{fmtDate(d.created_at)}</span>
              <StatusPill d={d} />
              <button className="icon-btn" title="Delete" onClick={async (e) => {
                e.preventDefault();
                if (confirm(`Delete "${d.name}"?`)) { await del(`/v1/dubbing/${d.dubbing_id}`); load(); }
              }}>🗑</button>
            </Link>
          ))}
        </div>
      )}
      {creating && <NewDub onClose={() => setCreating(false)} />}
    </>
  );
}

function NewDub({ onClose }: { onClose: () => void }) {
  const nav = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("");
  const [src, setSrc] = useState("");
  const [tgt, setTgt] = useState("bn");
  const [speakers, setSpeakers] = useState(0);
  const [mode, setMode] = useState<"clone" | "voice">("clone");
  const [voice, setVoice] = useState("");
  const [keepBg, setKeepBg] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    const f = new FormData();
    f.append("file", files[0]);
    f.append("name", name || files[0].name);
    f.append("source_lang", src || "auto");
    f.append("target_lang", tgt);
    f.append("num_speakers", String(speakers));
    f.append("drop_background_audio", String(!keepBg));
    if (mode === "voice" && voice) f.append("voice_id", voice);
    try {
      const r = await postForm<{ dubbing_id: string }>("/v1/dubbing", f);
      nav(`/dubbing/${r.dubbing_id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };
  return (
    <Modal title="New dubbing project" onClose={onClose}>
      <div className="field"><label>Project name</label><input value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional" /></div>
      <FileDrop accept="audio/*,video/*" files={files} onFiles={setFiles} hint="MP4, MOV, WEBM, MP3, WAV… up to 500 MB" />
      <div className="row gap wrap">
        <div className="field grow"><label>Source language</label><LanguageSelect value={src} onChange={setSrc} allowAuto /></div>
        <div className="field grow"><label>Target language</label><LanguageSelect value={tgt} onChange={setTgt} /></div>
      </div>
      <div className="field">
        <label>Speakers</label>
        <select value={speakers} onChange={(e) => setSpeakers(+e.target.value)}>
          <option value={0}>Detect automatically</option>
          {[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>
      <div className="field">
        <label>Voices</label>
        <div className="tabs">
          <button className={`tab ${mode === "clone" ? "active" : ""}`} onClick={() => setMode("clone")}>Clone original speakers</button>
          <button className={`tab ${mode === "voice" ? "active" : ""}`} onClick={() => setMode("voice")}>Use one library voice</button>
        </div>
      </div>
      {mode === "voice" && <VoicePicker value={voice} onChange={setVoice} />}
      <label className="check"><input type="checkbox" checked={keepBg} onChange={(e) => setKeepBg(e.target.checked)} /> Keep background music and sound effects</label>
      <ErrorBox error={error} />
      <div className="row end gap">
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className="btn primary" disabled={!files.length || busy} onClick={submit}>{busy ? <Spinner label="Uploading" /> : "Create dub"}</button>
      </div>
    </Modal>
  );
}
