"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { nextPoll } from "./poll";

// Загрузка по пути; опрос `pollMs`, пока `until(data)` не вернёт true (ход за человеком или запуск завершён).
// Ошибка не стирает последние данные, а опрос после неё продолжается с растущей паузой.
export function useApi<T>(path: string | null, opts: { pollMs?: number; until?: (d: T) => boolean } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [failures, setFailures] = useState(0);
  const [tick, setTick] = useState(0);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      setData(await api<T>(path));
      setError(null);
      setFailures(0);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, null));
      setFailures((n) => n + 1);
    } finally {
      setLoading(false);
      setTick((n) => n + 1);
    }
  }, [path]);

  useEffect(() => { setData(null); setError(null); setFailures(0); reload(); }, [reload]);

  useEffect(() => {
    const { pollMs, until } = optsRef.current;
    const delay = nextPoll({ pollMs, data, failures, until });
    if (delay === null) return;
    const t = setTimeout(reload, delay);
    return () => clearTimeout(t);
  }, [data, failures, tick, reload]);

  return { data, error, loading, reload, setData };
}
