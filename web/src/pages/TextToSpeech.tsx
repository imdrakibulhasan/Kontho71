import { useState } from "react";
import { postJSONForBlob } from "../api";
import { usePersistentState, useObjectUrls } from "../hooks";
import { AudioPlayer, ErrorBox, LanguageSelect, PageHeader, Slider, Spinner } from "../components/ui";
import { VoicePicker } from "../components/VoicePicker";

type Take = { url: string; text: string; voice: string; at: number };

const EXAMPLES = [
  "Welcome to Kontho, the open-source voice studio. Type anything and hear it in any voice.",
  "আমার সোনার বাংলা, আমি তোমায় ভালোবাসি। চিরদিন তোমার আকাশ, তোমার বাতাস, আমার প্রাণে বাজায় বাঁশি।",
  "Bonjour et bienvenue ! Aujourd'hui, nous allons découvrir ensemble une nouvelle façon de créer des voix.",
  "[laughter] Oh, you really thought that would work? [sigh] Alright, let's try it one more time.",
];

export default function TextToSpeech() {
  const [text, setText] = usePersistentState("tts.text", EXAMPLES[0]);
  const [voice, setVoice] = usePersistentState("tts.voice", "");
  const [model, setModel] = usePersistentState("tts.model", "kontho_v1");
  const [lang, setLang] = usePersistentState("tts.lang", "");
  const [settings, setSettings] = usePersistentState("tts.settings", { stability: 0.5, similarity_boost: 0.75, style: 0, speed: 1 });
  const [format, setFormat] = usePersistentState("tts.format", "mp3_44100_128");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [takes, setTakes] = useState<Take[]>([]);
  const toUrl = useObjectUrls();

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const { blob } = await postJSONForBlob(`/v1/text-to-speech/${voice}?output_format=${format}`, {
        text, model_id: model, language_code: lang || null, voice_settings: settings,
      });
      setTakes((t) => [{ url: toUrl(blob), text, voice, at: Date.now() }, ...t].slice(0, 10));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const ext = format.split("_")[0] === "opus" ? "ogg" : format.split("_")[0];

  return (
    <>
      <PageHeader title="Text to Speech" subtitle="Turn text into lifelike speech in 600+ languages, with any voice." />
      <div className="split">
        <section className="card grow">
          <textarea
            className="big-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Start typing here or paste any text you want to turn into lifelike speech…"
            maxLength={50000}
          />
          <div className="row between wrap gap">
            <div className="row gap wrap">
              {EXAMPLES.map((ex, i) => (
                <button key={i} className="chip" onClick={() => setText(ex)}>
                  {["English", "বাংলা", "Français", "Emotion tags"][i]}
                </button>
              ))}
            </div>
            <div className="row gap">
              <span className="muted small">{text.length.toLocaleString()} / 50,000</span>
              <button className="btn primary" disabled={busy || !text.trim() || !voice} onClick={generate}>
                {busy ? <Spinner label="Generating" /> : "Generate speech"}
              </button>
            </div>
          </div>
          <ErrorBox error={error} onClose={() => setError(null)} />
          {takes.length > 0 && (
            <div className="stack">
              <h3>Generations</h3>
              {takes.map((t) => (
                <div key={t.at} className="take">
                  <div className="small muted clamp">{t.text}</div>
                  <AudioPlayer src={t.url} filename={`kontho-${t.at}.${ext}`} />
                </div>
              ))}
            </div>
          )}
        </section>
        <aside className="card side">
          <div className="field">
            <label>Voice</label>
            <VoicePicker value={voice} onChange={setVoice} />
          </div>
          <div className="field">
            <label htmlFor="model">Model</label>
            <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="kontho_v1">Kontho v1 · best quality</option>
              <option value="kontho_turbo">Kontho Turbo · 2× faster</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="lang">Language</label>
            <LanguageSelect id="lang" value={lang} onChange={setLang} allowAuto />
          </div>
          <Slider label="Speed" value={settings.speed} min={0.5} max={2} step={0.05} onChange={(v) => setSettings({ ...settings, speed: v })} left="Slower" right="Faster" format={(v) => v.toFixed(2) + "×"} />
          <Slider label="Stability" value={settings.stability} min={0} max={1} step={0.05} onChange={(v) => setSettings({ ...settings, stability: v })} left="More variable" right="More stable" />
          <Slider label="Similarity" value={settings.similarity_boost} min={0} max={1} step={0.05} onChange={(v) => setSettings({ ...settings, similarity_boost: v })} left="Low" right="High" />
          <div className="field">
            <label htmlFor="fmt">Output format</label>
            <select id="fmt" value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="mp3_44100_128">MP3 · 44.1 kHz · 128 kbps</option>
              <option value="mp3_44100_192">MP3 · 44.1 kHz · 192 kbps</option>
              <option value="wav_44100">WAV · 44.1 kHz</option>
              <option value="wav_24000">WAV · 24 kHz</option>
              <option value="opus_48000_96">Opus · 48 kHz</option>
              <option value="flac_44100">FLAC · 44.1 kHz</option>
            </select>
          </div>
          <p className="muted small">
            Tip: add non-verbal tags like <code>[laughter]</code>, <code>[sigh]</code> or <code>[surprise-oh]</code> in your text.
          </p>
        </aside>
      </div>
    </>
  );
}
