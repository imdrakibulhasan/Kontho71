import { ReactNode, useEffect, useRef, useState } from "react";
import { mediaUrl } from "../api";
import { useLanguages } from "../hooks";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="row gap">{actions}</div>}
    </header>
  );
}

export function ErrorBox({ error, onClose }: { error: string | null; onClose?: () => void }) {
  if (!error) return null;
  return (
    <div className="error" role="alert">
      <span>{error}</span>
      {onClose && (
        <button className="icon-btn" onClick={onClose} aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="spinner-wrap">
      <span className="spinner" />
      {label && <span>{label}</span>}
    </span>
  );
}

export function Slider({
  label, value, min, max, step, onChange, left, right, format,
}: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void;
  left?: string; right?: string; format?: (v: number) => string;
}) {
  return (
    <div className="field">
      <div className="row between">
        <label>{label}</label>
        <span className="muted small">{format ? format(value) : value.toFixed(2)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} />
      {(left || right) && (
        <div className="row between small muted">
          <span>{left}</span>
          <span>{right}</span>
        </div>
      )}
    </div>
  );
}

export function LanguageSelect({
  value, onChange, allowAuto, autoLabel = "Auto-detect", id,
}: { value: string; onChange: (v: string) => void; allowAuto?: boolean; autoLabel?: string; id?: string }) {
  const langs = useLanguages();
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
      {allowAuto && <option value="">{autoLabel}</option>}
      {langs.map((l) => (
        <option key={l.language_id} value={l.language_id}>
          {l.name} {l.native_name !== l.name ? `· ${l.native_name}` : ""}
        </option>
      ))}
    </select>
  );
}

export function AudioPlayer({ src, filename, title }: { src: string; filename?: string; title?: string }) {
  const [url, setUrl] = useState<string | null>(src.startsWith("blob:") ? src : null);
  useEffect(() => {
    if (src.startsWith("blob:")) return setUrl(src);
    let alive = true;
    mediaUrl(src).then((u) => alive && setUrl(u)).catch(() => alive && setUrl(src));
    return () => {
      alive = false;
    };
  }, [src]);
  return (
    <div className="player">
      {title && <div className="player-title">{title}</div>}
      <div className="row gap">
        {url ? <audio controls src={url} preload="metadata" /> : <Spinner />}
        {url && filename && (
          <a className="btn ghost small" href={url} download={filename}>
            Download
          </a>
        )}
      </div>
    </div>
  );
}

export function FileDrop({
  accept, multiple, files, onFiles, hint,
}: { accept: string; multiple?: boolean; files: File[]; onFiles: (f: File[]) => void; hint?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      className={`drop ${over ? "over" : ""}`}
      onClick={() => input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const dropped = Array.from(e.dataTransfer.files);
        onFiles(multiple ? [...files, ...dropped] : dropped.slice(0, 1));
      }}
      role="button"
      tabIndex={0}
    >
      <input
        ref={input}
        type="file"
        hidden
        accept={accept}
        multiple={multiple}
        onChange={(e) => {
          const picked = Array.from(e.target.files || []);
          onFiles(multiple ? [...files, ...picked] : picked);
          e.target.value = "";
        }}
      />
      {files.length === 0 ? (
        <>
          <div className="drop-icon">⇪</div>
          <div>
            <strong>Click to upload</strong> or drag and drop
          </div>
          {hint && <div className="muted small">{hint}</div>}
        </>
      ) : (
        <ul className="file-list" onClick={(e) => e.stopPropagation()}>
          {files.map((f, i) => (
            <li key={i}>
              <span>{f.name}</span>
              <span className="muted small">{(f.size / 1024 / 1024).toFixed(1)} MB</span>
              <button className="icon-btn" onClick={() => onFiles(files.filter((_, j) => j !== i))} aria-label="Remove">
                ×
              </button>
            </li>
          ))}
          {multiple && (
            <li>
              <button className="btn ghost small" onClick={() => input.current?.click()}>
                + Add more
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

/** Record from the microphone; returns a File (webm/ogg) via onRecorded. */
export function Recorder({ onRecorded }: { onRecorded: (f: File) => void }) {
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const [secs, setSecs] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<number>();
  const start = async () => {
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const r = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const type = r.mimeType || "audio/webm";
        const ext = type.includes("ogg") ? "ogg" : type.includes("mp4") ? "m4a" : "webm";
        onRecorded(new File([new Blob(chunks, { type })], `recording-${Date.now()}.${ext}`, { type }));
      };
      r.start();
      setRec(r);
      setSecs(0);
      timer.current = window.setInterval(() => setSecs((s) => s + 1), 1000);
    } catch (e) {
      setErr("Microphone not available: " + (e as Error).message);
    }
  };
  const stop = () => {
    rec?.stop();
    setRec(null);
    window.clearInterval(timer.current);
  };
  return (
    <div className="row gap">
      {rec ? (
        <button className="btn danger" onClick={stop}>
          ■ Stop ({secs}s)
        </button>
      ) : (
        <button className="btn ghost" onClick={start}>
          ● Record audio
        </button>
      )}
      {err && <span className="small error-text">{err}</span>}
    </div>
  );
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className={`modal ${wide ? "wide" : ""}`} onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-label={title}>
        <div className="row between modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

export const fmtTime = (t: number) => {
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
};

export const fmtDate = (unix: number) => new Date(unix * 1000).toLocaleString();
