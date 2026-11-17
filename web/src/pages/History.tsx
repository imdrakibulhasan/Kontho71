import { useEffect, useState } from "react";
import { del, getJSON, HistoryItem } from "../api";
import { AudioPlayer, Empty, ErrorBox, fmtDate, PageHeader, Spinner } from "../components/ui";

const KINDS: Record<string, string> = { "": "All", tts: "Text to speech", sts: "Voice changer", sfx: "Sound effects", isolation: "Voice isolator", stt: "Transcripts" };

export default function History() {
  const [kind, setKind] = useState("");
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [more, setMore] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = (after?: string) => {
    setLoading(true);
    const q = new URLSearchParams({ page_size: "30" });
    if (kind) q.set("kind", kind);
    if (after) q.set("start_after_history_item_id", after);
    getJSON<{ history: HistoryItem[]; has_more: boolean; last_history_item_id: string }>(`/v1/history?${q}`)
      .then((r) => {
        setItems((x) => (after ? [...x, ...r.history] : r.history));
        setMore(r.has_more ? r.last_history_item_id : null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => load(), [kind]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <PageHeader title="History" subtitle="Everything you generated, stored on your own server." />
      <div className="tabs mb">
        {Object.entries(KINDS).map(([k, label]) => (
          <button key={k} className={`tab ${kind === k ? "active" : ""}`} onClick={() => setKind(k)}>{label}</button>
        ))}
      </div>
      <ErrorBox error={error} />
      {!loading && items.length === 0 && <Empty title="Nothing here yet" />}
      <div className="stack">
        {items.map((h) => (
          <div key={h.history_item_id} className="card history-item">
            <div className="row between gap">
              <div className="grow">
                <span className="tag">{KINDS[h.kind] || h.kind}</span>{" "}
                {h.voice_name && <strong>{h.voice_name}</strong>}
                <span className="muted small"> · {fmtDate(h.date_unix)}</span>
              </div>
              <button className="icon-btn" title="Delete" onClick={async () => {
                await del(`/v1/history/${h.history_item_id}`);
                setItems((x) => x.filter((i) => i.history_item_id !== h.history_item_id));
              }}>🗑</button>
            </div>
            {h.text && <p className="small clamp">{h.text}</p>}
            {h.audio_url && <AudioPlayer src={h.audio_url} filename={`${h.history_item_id}.wav`} />}
          </div>
        ))}
      </div>
      {loading && <Spinner label="Loading" />}
      {more && !loading && <button className="btn ghost" onClick={() => load(more)}>Load more</button>}
    </>
  );
}
