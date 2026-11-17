import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Dub, getJSON, mediaUrl, Segment, sendJSON } from "../api";
import { useVoices } from "../hooks";
import { ErrorBox, fmtTime, PageHeader, Spinner } from "../components/ui";
import { StatusPill } from "./Dubbing";

type SegResp = { segments: Segment[]; speakers: string[]; source_lang: string; target_lang: string };

export default function DubbingProject() {
  const { id } = useParams();
  const [dub, setDub] = useState<Dub | null>(null);
  const [segs, setSegs] = useState<SegResp | null>(null);
  const [media, setMedia] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const { voices } = useVoices();

  const load = useCallback(async () => {
    try {
      const d = await getJSON<Dub>(`/v1/dubbing/${id}`);
      setDub(d);
      return d;
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    let t: number;
    const tick = async () => {
      const d = await load();
      if (d?.status === "dubbing") t = window.setTimeout(tick, 2000);
      else if (d?.status === "dubbed") {
        setSegs(await getJSON<SegResp>(`/v1/dubbing/${id}/segments`));
        setVersion((v) => v + 1);
      }
    };
    tick();
    return () => window.clearTimeout(t);
  }, [id, load]);

  useEffect(() => {
    if (dub?.status !== "dubbed") return;
    const lang = dub.target_languages[0];
    mediaUrl(`/v1/dubbing/${id}/audio/${lang}?v=${version}`).then(setMedia);
  }, [dub?.status, id, version, dub?.target_languages]);

  const patch = async (i: number, body: Partial<Segment> & { retranslate?: boolean }) => {
    try {
      const seg = await sendJSON<Segment>(`/v1/dubbing/${id}/segments/${i}`, body, "PATCH");
      setSegs((s) => s && { ...s, segments: s.segments.map((x) => (x.index === i ? seg : x)) });
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const render = async () => {
    try {
      await sendJSON(`/v1/dubbing/${id}/render`, {});
      setDub((d) => d && { ...d, status: "dubbing", progress: 0, message: "Queued" });
      const poll = async () => {
        const d = await load();
        if (d?.status === "dubbing") window.setTimeout(poll, 2000);
        else if (d?.status === "dubbed") {
          setSegs(await getJSON<SegResp>(`/v1/dubbing/${id}/segments`));
          setVersion((v) => v + 1);
        }
      };
      poll();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (!dub) return error ? <ErrorBox error={error} /> : <Spinner label="Loading" />;
  const lang = dub.target_languages[0];
  const dirty = segs?.segments.some((s) => s.dirty);
  return (
    <>
      <PageHeader
        title={dub.name}
        subtitle={`${dub.source_language || "auto"} → ${lang}${dub.num_speakers ? ` · ${dub.num_speakers} speaker(s)` : ""}`}
        actions={<><StatusPill d={dub} /><Link className="btn ghost" to="/dubbing">← All projects</Link></>}
      />
      <ErrorBox error={error} onClose={() => setError(null)} />
      {dub.status === "dubbing" && (
        <div className="card">
          <div className="row between"><strong>{dub.message}</strong><span>{Math.round(dub.progress * 100)}%</span></div>
          <div className="progress"><div style={{ width: `${dub.progress * 100}%` }} /></div>
          <p className="muted small">Separating voices, transcribing, translating and re-voicing. This runs on your server and can take a few minutes.</p>
        </div>
      )}
      {dub.status === "failed" && <ErrorBox error={`Dubbing failed: ${dub.error}`} />}
      {dub.status === "dubbed" && media && (
        <div className="card">
          {dub.is_video ? <video className="video" controls src={media} /> : <audio controls src={media} />}
          <div className="row gap wrap">
            <a className="btn primary small" href={media} download={`dubbed_${lang}.${dub.is_video ? "mp4" : "mp3"}`}>Download {dub.is_video ? "video" : "audio"}</a>
            <DownloadLink href={`/v1/dubbing/${id}/audio/${lang}?kind=audio`} name={`dubbed_${lang}.mp3`} label="Audio only (MP3)" />
            <DownloadLink href={`/v1/dubbing/${id}/transcript/${lang}?format_type=srt`} name={`subtitles_${lang}.srt`} label="Subtitles (SRT)" />
            <DownloadLink href={`/v1/dubbing/${id}/transcript/${lang}?format_type=vtt`} name={`subtitles_${lang}.vtt`} label="Subtitles (VTT)" />
          </div>
        </div>
      )}
      {segs && (
        <section className="card">
          <div className="row between wrap gap">
            <h3>Dubbing studio · {segs.segments.length} segments</h3>
            <button className="btn primary" disabled={!dirty || dub.status === "dubbing"} onClick={render}>
              {dub.status === "dubbing" ? <Spinner label="Rendering" /> : dirty ? "Re-render changed segments" : "Up to date"}
            </button>
          </div>
          <p className="muted small">Edit any translation, timing or voice, then re-render. Only changed segments are re-generated.</p>
          <div className="segments">
            {segs.segments.map((s) => (
              <div key={s.index} className={`segment ${s.dirty ? "dirty" : ""}`}>
                <div className="segment-meta">
                  <span className={`speaker s${+s.speaker.replace(/\D/g, "") % 6}`}>{s.speaker.replace("_", " ")}</span>
                  <span className="muted small">{fmtTime(s.start)} – {fmtTime(s.end)}</span>
                  <select className="small-select" value={s.voice_id || ""} onChange={(e) => patch(s.index, { voice_id: e.target.value || null } as Partial<Segment>)}>
                    <option value="">Cloned speaker voice</option>
                    {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
                  </select>
                </div>
                <div className="segment-texts">
                  <div className="muted small">{s.text}</div>
                  <textarea
                    rows={2}
                    defaultValue={s.translation}
                    key={s.translation}
                    onBlur={(e) => e.target.value !== s.translation && patch(s.index, { translation: e.target.value })}
                  />
                  <button className="btn ghost small" onClick={() => patch(s.index, { retranslate: true })}>↻ Re-translate</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function DownloadLink({ href, name, label }: { href: string; name: string; label: string }) {
  return (
    <button className="btn ghost small" onClick={async () => {
      const a = document.createElement("a");
      a.href = await mediaUrl(href);
      a.download = name;
      a.click();
    }}>{label}</button>
  );
}
