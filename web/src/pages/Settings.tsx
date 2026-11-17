import { useEffect, useState } from "react";
import { api, del, getApiKey, getJSON, sendJSON, setApiKey } from "../api";
import { ErrorBox, fmtDate, PageHeader } from "../components/ui";

type Key = { id: string; name: string; prefix: string; created_at: number; last_used_at: number | null };
type Rule = { id: string; term: string; replacement: string; language: string };
type Status = Awaited<ReturnType<typeof api.status>>;

export default function Settings() {
  const [status, setStatus] = useState<Status | null>(null);
  const [keys, setKeys] = useState<Key[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [keyName, setKeyName] = useState("My app");
  const [myKey, setMyKey] = useState(getApiKey());
  const [term, setTerm] = useState("");
  const [repl, setRepl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    api.status().then(setStatus).catch((e) => setError(e.message));
    getJSON<{ keys: Key[] }>("/v1/api-keys").then((r) => setKeys(r.keys)).catch(() => {});
    getJSON<{ rules: Rule[] }>("/v1/pronunciation").then((r) => setRules(r.rules)).catch(() => {});
  };
  useEffect(load, []);
  const origin = window.location.origin;
  return (
    <>
      <PageHeader title="Settings & API" subtitle="Engines, API keys, pronunciation dictionary and integration." />
      <ErrorBox error={error} onClose={() => setError(null)} />
      <div className="grid two">
        <section className="card">
          <h3>Server</h3>
          {status ? (
            <table className="kv">
              <tbody>
                <tr><td>Version</td><td>{status.version}</td></tr>
                <tr><td>Device</td><td>{status.device}</td></tr>
                <tr><td>ffmpeg</td><td>{status.ffmpeg ? "✓ found" : "✗ missing"}</td></tr>
                {Object.entries(status.engines).map(([k, e]) => (
                  <tr key={k}><td>{k}</td><td><code>{e.engine}</code> {e.loaded ? <span className="pill ok">loaded</span> : <span className="muted small">loads on first use</span>}</td></tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">Loading…</p>}
        </section>
        <section className="card">
          <h3>This browser's API key</h3>
          <p className="muted small">Needed only when the server runs with <code>KONTHO_AUTH=true</code>.</p>
          <div className="row gap">
            <input className="grow" type="password" value={myKey} onChange={(e) => setMyKey(e.target.value)} placeholder="kt_…" />
            <button className="btn primary" onClick={() => { setApiKey(myKey.trim()); load(); }}>Save</button>
          </div>
        </section>
        <section className="card">
          <h3>API keys</h3>
          <div className="row gap">
            <input className="grow" value={keyName} onChange={(e) => setKeyName(e.target.value)} />
            <button className="btn primary" onClick={async () => {
              try {
                const r = await sendJSON<{ api_key: string }>("/v1/api-keys", { name: keyName });
                setNewKey(r.api_key);
                load();
              } catch (e) { setError((e as Error).message); }
            }}>Create key</button>
          </div>
          {newKey && <div className="notice">Copy this key now, it won't be shown again:<br /><code className="break">{newKey}</code></div>}
          <ul className="list">
            {keys.map((k) => (
              <li key={k.id} className="row between">
                <span><strong>{k.name}</strong> <code className="muted">{k.prefix}…</code><br /><span className="muted small">created {fmtDate(k.created_at)}{k.last_used_at ? ` · last used ${fmtDate(k.last_used_at)}` : ""}</span></span>
                <button className="btn ghost small" onClick={async () => { await del(`/v1/api-keys/${k.id}`); load(); }}>Revoke</button>
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h3>Pronunciation dictionary</h3>
          <p className="muted small">Replace words before speech is generated (acronyms, names, brand words).</p>
          <div className="row gap wrap">
            <input className="grow" placeholder="Word, e.g. AB" value={term} onChange={(e) => setTerm(e.target.value)} />
            <input className="grow" placeholder="Say it as, e.g. Amar Bangla" value={repl} onChange={(e) => setRepl(e.target.value)} />
            <button className="btn primary" disabled={!term || !repl} onClick={async () => {
              await sendJSON("/v1/pronunciation", { term, replacement: repl });
              setTerm(""); setRepl(""); load();
            }}>Add</button>
          </div>
          <ul className="list">
            {rules.map((r) => (
              <li key={r.id} className="row between"><span><strong>{r.term}</strong> → {r.replacement}</span>
                <button className="btn ghost small" onClick={async () => { await del(`/v1/pronunciation/${r.id}`); load(); }}>Remove</button></li>
            ))}
          </ul>
        </section>
      </div>
      <section className="card">
        <h3>Use the API</h3>
        <p className="muted small">The API is ElevenLabs-compatible. Existing SDKs work by changing the base URL. Full reference: <a href="/docs" target="_blank" rel="noreferrer">/docs</a>.</p>
        <pre className="code">{`curl -X POST "${origin}/v1/text-to-speech/premade_aria" \\
  -H "xi-api-key: $KONTHO_API_KEY" -H "Content-Type: application/json" \\
  -d '{"text": "Hello from Kontho!", "model_id": "kontho_v1"}' --output hello.mp3`}</pre>
        <pre className="code">{`# Python - official ElevenLabs SDK, pointed at your server
from elevenlabs.client import ElevenLabs
client = ElevenLabs(api_key="kt_...", base_url="${origin}")
audio = client.text_to_speech.convert(voice_id="premade_aria", text="আমার সোনার বাংলা", model_id="kontho_v1")`}</pre>
      </section>
    </>
  );
}
