// Minimal typed client for the Kontho (ElevenLabs-compatible) API.

export type Voice = {
  voice_id: string;
  name: string;
  category: "premade" | "cloned" | "designed";
  description: string;
  labels: Record<string, string>;
  language: string;
  preview_url: string;
  created_at_unix: number;
};

export type VoiceSettings = { stability: number; similarity_boost: number; style: number; speed: number };
export type Language = { language_id: string; name: string; native_name: string };
export type HistoryItem = {
  history_item_id: string;
  kind: string;
  voice_name: string | null;
  text: string | null;
  date_unix: number;
  audio_url: string | null;
  settings: Record<string, unknown>;
};
export type Segment = {
  index: number;
  start: number;
  end: number;
  speaker: string;
  text: string;
  translation: string;
  voice_id: string | null;
  dirty: boolean;
};
export type Dub = {
  dubbing_id: string;
  name: string;
  status: "dubbing" | "dubbed" | "failed";
  progress: number;
  message: string;
  error: string | null;
  source_language: string | null;
  target_languages: string[];
  is_video: boolean;
  duration: number | null;
  num_speakers: number | null;
  created_at: number;
};
export type Transcript = {
  language_code: string;
  text: string;
  duration: number;
  segments: { start: number; end: number; text: string; speaker_id: string }[];
};

const KEY = "kontho.apiKey";
export const getApiKey = () => {
  try {
    return localStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
};
export const setApiKey = (k: string) => {
  try {
    k ? localStorage.setItem(KEY, k) : localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable */
  }
};

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const k = getApiKey();
  return k ? { "xi-api-key": k, ...extra } : extra;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function check(res: Response): Promise<Response> {
  if (res.ok) return res;
  let msg = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    const d = body.detail;
    msg = typeof d === "string" ? d : d?.message || (Array.isArray(d) ? d.map((x: { msg: string }) => x.msg).join(", ") : msg);
  } catch {
    /* not json */
  }
  throw new ApiError(res.status, msg);
}

export async function getJSON<T>(path: string): Promise<T> {
  return (await check(await fetch(path, { headers: headers() }))).json();
}

export async function sendJSON<T>(path: string, body: unknown, method = "POST"): Promise<T> {
  const res = await fetch(path, { method, headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body) });
  return (await check(res)).json();
}

export async function postJSONForBlob(path: string, body: unknown): Promise<{ blob: Blob; historyId: string | null }> {
  const res = await check(
    await fetch(path, { method: "POST", headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body) }),
  );
  return { blob: await res.blob(), historyId: res.headers.get("history-item-id") };
}

export async function postForm<T>(path: string, form: FormData): Promise<T> {
  return (await check(await fetch(path, { method: "POST", headers: headers(), body: form }))).json();
}

export async function postFormForBlob(path: string, form: FormData): Promise<{ blob: Blob; historyId: string | null }> {
  const res = await check(await fetch(path, { method: "POST", headers: headers(), body: form }));
  return { blob: await res.blob(), historyId: res.headers.get("history-item-id") };
}

export async function postFormForText(path: string, form: FormData): Promise<string> {
  return (await check(await fetch(path, { method: "POST", headers: headers(), body: form }))).text();
}

export async function del(path: string): Promise<void> {
  await check(await fetch(path, { method: "DELETE", headers: headers() }));
}

/** Fetch a protected media URL as an object URL (needed when API keys are enabled). */
export async function mediaUrl(path: string): Promise<string> {
  if (!getApiKey()) return path;
  const res = await check(await fetch(path, { headers: headers() }));
  return URL.createObjectURL(await res.blob());
}

export const api = {
  voices: () => getJSON<{ voices: Voice[] }>("/v1/voices").then((r) => r.voices),
  languages: () => getJSON<{ languages: Language[] }>("/v1/languages").then((r) => r.languages),
  status: () => getJSON<{ version: string; device: string; ffmpeg: boolean; engines: Record<string, { engine: string; loaded: boolean; available: string[] }> }>("/v1/system/status"),
};
