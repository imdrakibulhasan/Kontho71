import { useState } from "react";
import { postFormForBlob } from "../api";
import { usePersistentState, useObjectUrls } from "../hooks";
import { AudioPlayer, ErrorBox, FileDrop, PageHeader, Recorder, Slider, Spinner } from "../components/ui";
import { VoicePicker } from "../components/VoicePicker";

export default function VoiceChanger() {
  const [files, setFiles] = useState<File[]>([]);
  const [voice, setVoice] = usePersistentState("sts.voice", "");
  const [similarity, setSimilarity] = useState(0.75);
  const [denoise, setDenoise] = useState(false);
  const [keepBg, setKeepBg] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [out, setOut] = useState<{ src: string; result: string } | null>(null);
  const toUrl = useObjectUrls();

  const run = async () => {
    setBusy(true);
    setError(null);
    const f = new FormData();
    f.append("audio", files[0]);
    f.append("voice_settings", JSON.stringify({ similarity_boost: similarity, stability: 0.5 }));
    f.append("remove_background_noise", String(denoise));
    f.append("keep_background", String(keepBg));
    try {
      const { blob } = await postFormForBlob(`/v1/speech-to-speech/${voice}`, f);
      setOut({ src: toUrl(files[0]), result: toUrl(blob) });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader title="Voice Changer" subtitle="Say it your way, in any voice. Keeps your words and timing, swaps the voice." />
      <div className="split">
        <section className="card grow">
          <FileDrop accept="audio/*,video/*" files={files} onFiles={setFiles} hint="A recording of speech (any language)" />
          <Recorder onRecorded={(f) => setFiles([f])} />
          <ErrorBox error={error} onClose={() => setError(null)} />
          {out && (
            <div className="stack">
              <AudioPlayer src={out.src} title="Original" />
              <AudioPlayer src={out.result} title="Converted" filename="voice-changed.mp3" />
            </div>
          )}
        </section>
        <aside className="card side">
          <div className="field"><label>Target voice</label><VoicePicker value={voice} onChange={setVoice} /></div>
          <Slider label="Similarity" value={similarity} min={0} max={1} step={0.05} onChange={setSimilarity} left="Low" right="High" />
          <label className="check"><input type="checkbox" checked={denoise} onChange={(e) => setDenoise(e.target.checked)} /> Remove background noise</label>
          <label className="check"><input type="checkbox" checked={keepBg} onChange={(e) => setKeepBg(e.target.checked)} /> Keep music / background</label>
          <button className="btn primary full" disabled={!files.length || !voice || busy} onClick={run}>
            {busy ? <Spinner label="Converting" /> : "Change voice"}
          </button>
          <p className="muted small">How it works: speech is transcribed with timestamps, then every phrase is re-spoken by the target voice in exactly the same time slot.</p>
        </aside>
      </div>
    </>
  );
}
