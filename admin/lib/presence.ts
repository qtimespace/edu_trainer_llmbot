"use client";
import { useEffect } from "react";
import { api } from "./api";
import { pageState } from "./attention";

// Пока вкладка ученика открыта — пинг раз в 15 с: в его комнате горит свет и сидят агенты. С пингом уходит, куда
// смотрит вкладка (в фокусе / окно не в фокусе / скрыта); смена состояния отправляется сразу, не дожидаясь пинга.
export function usePresence(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    const state = () => pageState(document.visibilityState, document.hasFocus());
    const ping = () => { api("/presence/ping", { method: "POST", body: { state: state() } }).catch(() => undefined); };
    let last = state();
    const changed = () => {
      const now = state();
      if (now !== last) { last = now; ping(); }
    };
    ping();
    const t = setInterval(ping, 15_000);
    document.addEventListener("visibilitychange", changed);
    window.addEventListener("focus", changed);
    window.addEventListener("blur", changed);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", changed);
      window.removeEventListener("focus", changed);
      window.removeEventListener("blur", changed);
    };
  }, [enabled]);
}
