import { useState } from "react";
import { postForm, Transcript } from "../api";
import { AudioPlayer, ErrorBox, FileDrop, fmtTime, LanguageSelect, PageHeader, Recorder, Spinner } from "../components/ui";
import { useObjectUrls } from "../hooks";

function srt(t: Transcript, speakers: boolean) {
  const ts = (x: number) => new Date(x * 1000).toISOString().slice(11, 23).replace(".", ",");
  return t.segments.map((s, i) => `${i + 1}\n${ts(s.start)} --> ${ts(s.end)}\n${speakers ? `[${s.speaker_id}] ` : ""}${s.text}\n`).join("\n");
}

export default function SpeechToText() {
  const [files, setFiles] = useState<File[]>([]);
  const [lang, setLang] = useState("");
  const [diarize, setDiarize] = useState(false);
  const [speakers, setSpeakers] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Transcript | null>(null);
  const [srcUrl, setSrcUrl] = useState<string | null>(null);
  const toUrl = useObjectUrls();

  const run = async () => {
    setBusy(true);
    setError(null);
    const f = new FormData();
    f.append("file", files[0]);
    if (lang) f.append("language_code", lang);
    f.append("diarize", String(diarize));
    if (diarize && speakers) f.append("num_speakers", String(speakers));
    try {
      setResult(await postForm<Transcript>("/v1/speech-to-text", f));
      setSrcUrl(toUrl(files[0]));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const download = (content: string, name: string) => {
    const a = document.createElement("a");
    a.href = toUrl(new Blob([content], { type: "text/plain" }));
    a.download = name;
    a.click();
  };

  return (
    <>
      <PageHeader title="Speech to Text" subtitle="Transcribe audio and video in 99 languages with word timestamps and speaker labels." />
      <div className="split">
        <section className="card grow">
          <FileDrop accept="audio/*,video/*" files={files} onFiles={setFiles} hint="Audio or video, up to 500 MB" />
          <Recorder onRecorded={(f) => setFiles([f])} />
          <ErrorBox error={error} onClose={() => setError(null)} />
          {result && (
            <div className="stack">
              <div className="row between wrap gap">
                <h3>Transcript <span className="muted small">· {result.language_code} · {fmtTime(result.duration)}</span></h3>
                <div className="row gap">
                  <button className="btn ghost small" onClick={() => navigator.clipboard.writeText(result.text)}>Copy</button>
                  <button className="btn ghost small" onClick={() => download(result.text, "transcript.txt")}>TXT</button>
                  <button className="btn ghost small" onClick={() => download(srt(result, diarize), "transcript.srt")}>SRT</button>
                  <button className="btn ghost small" onClick={() => download(JSON.stringify(result, null, 2), "transcript.json")}>JSON</button>
                </div>
              </div>
              {srcUrl && <AudioPlayer src={srcUrl} />}
              <div className="transcript">
                {result.segments.map((s, i) => (
                  <div key={i} className="seg">
                    <span className="seg-time">{fmtTime(s.start)}</span>
                    {diarize && <span className={`speaker s${+s.speaker_id.replace(/\D/g, "") % 6}`}>{s.speaker_id.replace("_", " ")}</span>}
                    <span>{s.text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
        <aside className="card side">
          <div className="field">
            <label>Language</label>
            <LanguageSelect value={lang} onChange={setLang} allowAuto />
          </div>
          <label className="check"><input type="checkbox" checked={diarize} onChange={(e) => setDiarize(e.target.checked)} /> Identify speakers</label>
          {diarize && (
            <div className="field">
              <label>Number of speakers</label>
              <select value={speakers} onChange={(e) => setSpeakers(+e.target.value)}>
                <option value={0}>Detect automatically</option>
                {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          )}
          <button className="btn primary full" disabled={!files.length || busy} onClick={run}>
            {busy ? <Spinner label="Transcribing" /> : "Transcribe"}
          </button>
        </aside>
      </div>
    </>
  );
}
