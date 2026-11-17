import { useState } from "react";
import { postFormForBlob } from "../api";
import { useObjectUrls } from "../hooks";
import { AudioPlayer, ErrorBox, FileDrop, PageHeader, Spinner } from "../components/ui";

export default function VoiceIsolator() {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [out, setOut] = useState<{ src: string; vocals: string; bg: string } | null>(null);
  const toUrl = useObjectUrls();
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const get = async (stem: string) => {
        const f = new FormData();
        f.append("audio", files[0]);
        return (await postFormForBlob(`/v1/audio-isolation?stem=${stem}`, f)).blob;
      };
      const vocals = await get("vocals");
      const bg = await get("background");
      setOut({ src: toUrl(files[0]), vocals: toUrl(vocals), bg: toUrl(bg) });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader title="Voice Isolator" subtitle="Extract crystal-clear speech from any audio: remove music, noise and background." />
      <section className="card narrow">
        <FileDrop accept="audio/*,video/*" files={files} onFiles={setFiles} hint="Audio or video with speech" />
        <button className="btn primary" disabled={!files.length || busy} onClick={run}>
          {busy ? <Spinner label="Separating" /> : "Isolate voice"}
        </button>
        <ErrorBox error={error} onClose={() => setError(null)} />
        {out && (
          <div className="stack">
            <AudioPlayer src={out.src} title="Original" />
            <AudioPlayer src={out.vocals} title="Isolated voice" filename="voice.mp3" />
            <AudioPlayer src={out.bg} title="Background (music & noise)" filename="background.mp3" />
          </div>
        )}
      </section>
    </>
  );
}
