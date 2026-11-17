import { useCallback, useEffect, useRef, useState } from "react";
import { api, EmotionInfo, Language, Voice } from "./api";

let voicesCache: Voice[] | null = null;
let langCache: Language[] | null = null;
let emoCache: EmotionInfo[] | null = null;

export function useEmotionCatalog() {
  const [emos, setEmos] = useState<EmotionInfo[]>(emoCache || []);
  useEffect(() => {
    if (!emoCache) api.emotions().then((e) => setEmos((emoCache = e))).catch(() => {});
  }, []);
  return emos;
}
const listeners = new Set<() => void>();

export function refreshVoices() {
  voicesCache = null;
  listeners.forEach((l) => l());
}

export function useVoices() {
  const [voices, setVoices] = useState<Voice[]>(voicesCache || []);
  const [loading, setLoading] = useState(!voicesCache);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    setLoading(true);
    api
      .voices()
      .then((v) => {
        voicesCache = v;
        setVoices(v);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!voicesCache) load();
    listeners.add(load);
    return () => {
      listeners.delete(load);
    };
  }, [load]);
  return { voices, loading, error, reload: refreshVoices };
}

export function useLanguages() {
  const [langs, setLangs] = useState<Language[]>(langCache || []);
  useEffect(() => {
    if (!langCache) api.languages().then((l) => setLangs((langCache = l))).catch(() => {});
  }, []);
  return langs;
}

/** Track object URLs and revoke them on unmount. */
export function useObjectUrls() {
  const urls = useRef<string[]>([]);
  useEffect(() => () => urls.current.forEach((u) => URL.revokeObjectURL(u)), []);
  return useCallback((blob: Blob) => {
    const u = URL.createObjectURL(blob);
    urls.current.push(u);
    return u;
  }, []);
}

export function usePersistentState<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        localStorage.setItem(key, JSON.stringify(v));
      } catch {
        /* ignore */
      }
    },
    [key],
  );
  return [value, set];
}
