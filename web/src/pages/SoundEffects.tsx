import { useState } from "react";
import { postJSONForBlob } from "../api";
import { useObjectUrls } from "../hooks";
import { AudioPlayer, ErrorBox, PageHeader, Slider, Spinner } from "../components/ui";

const IDEAS = ["Thunderstorm with heavy rain on a tin roof", "Footsteps on gravel, slow walk", "Old wooden door creaking open",
  "Busy Dhaka street with rickshaw bells and traffic", "Cinematic whoosh transition", "Crowd cheering in a stadium",
  "Birds chirping at dawn in a village", "Sci-fi laser blast"];

export default function SoundEffects() {
  const [prompt, setPrompt] = useState(IDEAS[0]);
  const [auto, setAuto] = useState(true);
  const [duration, setDuration] = useState(5);
  const [influence, setInfluence] = useState(0.3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<{ url: string; prompt: string; at: number }[]>([]);
  const toUrl = useObjectUrls();
  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const { blob } = await postJSONForBlob("/v1/sound-generation", {
        text: prompt, duration_seconds: auto ? null : duration, prompt_influence: influence,
      });
      setResults((r) => [{ url: toUrl(blob), prompt, at: Date.now() }, ...r]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader title="Sound Effects" subtitle="Describe a sound and generate it: foley, ambience, transitions, game audio." />
      <div className="split">
        <section className="card grow">
          <textarea className="big-text short" value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Describe the sound…" />
          <div className="row gap wrap">
            {IDEAS.map((i) => <button key={i} className="chip" onClick={() => setPrompt(i)}>{i}</button>)}
          </div>
          <ErrorBox error={error} onClose={() => setError(null)} />
          {results.map((r) => (
            <div key={r.at} className="take">
              <div className="small muted">{r.prompt}</div>
              <AudioPlayer src={r.url} filename={`sfx-${r.at}.mp3`} />
            </div>
          ))}
        </section>
        <aside className="card side">
          <label className="check"><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> Default duration (5 s)</label>
          {!auto && <Slider label="Duration" value={duration} min={0.5} max={30} step={0.5} onChange={setDuration} format={(v) => `${v.toFixed(1)} s`} />}
          <Slider label="Prompt influence" value={influence} min={0} max={1} step={0.05} onChange={setInfluence} left="More creative" right="Follow prompt" />
          <button className="btn primary full" disabled={!prompt.trim() || busy} onClick={run}>
            {busy ? <Spinner label="Generating" /> : "Generate sound"}
          </button>
        </aside>
      </div>
    </>
  );
}
