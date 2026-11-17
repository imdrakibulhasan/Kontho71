import { useEffect, useMemo, useRef, useState } from "react";
import { mediaUrl, Voice } from "../api";
import { useVoices } from "../hooks";

export function voiceInitials(name: string) {
  return name.split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
}

export function VoiceAvatar({ voice }: { voice: Voice }) {
  let h = 0;
  for (const c of voice.voice_id) h = (h * 31 + c.charCodeAt(0)) % 360;
  return (
    <span className="avatar" style={{ background: `linear-gradient(135deg, hsl(${h} 65% 55%), hsl(${(h + 50) % 360} 70% 45%))` }}>
      {voiceInitials(voice.name)}
    </span>
  );
}

export function PreviewButton({ voice }: { voice: Voice }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "playing">("idle");
  useEffect(() => () => audio.current?.pause(), []);
  const toggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (state === "playing") {
      audio.current?.pause();
      setState("idle");
      return;
    }
    setState("loading");
    try {
      const a = new Audio(await mediaUrl(voice.preview_url));
      audio.current = a;
      a.onended = () => setState("idle");
      await a.play();
      setState("playing");
    } catch {
      setState("idle");
    }
  };
  return (
    <button className="icon-btn play" onClick={toggle} aria-label={`Preview ${voice.name}`} title="Preview">
      {state === "playing" ? "❚❚" : state === "loading" ? "…" : "▶"}
    </button>
  );
}

export function VoicePicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { voices, loading } = useVoices();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const selected = voices.find((v) => v.voice_id === value);
  const filtered = useMemo(
    () => voices.filter((v) => (v.name + " " + v.description + " " + Object.values(v.labels).join(" ")).toLowerCase().includes(q.toLowerCase())),
    [voices, q],
  );
  useEffect(() => {
    if (!value && voices.length) onChange(voices[0].voice_id);
  }, [voices, value, onChange]);
  return (
    <div className="voice-picker">
      <button className="voice-picker-btn" onClick={() => setOpen(!open)} aria-expanded={open}>
        {selected ? (
          <>
            <VoiceAvatar voice={selected} />
            <span className="grow left">
              <strong>{selected.name}</strong>
              <span className="muted small block">{selected.category}</span>
            </span>
          </>
        ) : (
          <span className="grow left muted">{loading ? "Loading voices…" : "Select a voice"}</span>
        )}
        <span className="muted">▾</span>
      </button>
      {open && (
        <div className="voice-menu">
          <input autoFocus placeholder="Search voices…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="voice-menu-list">
            {filtered.map((v) => (
              <div
                key={v.voice_id}
                className={`voice-option ${v.voice_id === value ? "active" : ""}`}
                onClick={() => {
                  onChange(v.voice_id);
                  setOpen(false);
                }}
              >
                <VoiceAvatar voice={v} />
                <span className="grow">
                  <strong>{v.name}</strong>
                  <span className="muted small block">
                    {v.category}
                    {v.labels.gender ? ` · ${v.labels.gender}` : ""}
                    {v.labels.accent ? ` · ${v.labels.accent}` : ""}
                  </span>
                </span>
                <PreviewButton voice={v} />
              </div>
            ))}
            {!filtered.length && <div className="muted small pad">No voices match.</div>}
          </div>
        </div>
      )}
    </div>
  );
}
