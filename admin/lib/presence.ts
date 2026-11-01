"use client";
import { useEffect } from "react";
import { api } from "./api";

// Пока вкладка ученика открыта — пинг раз в 15 с: в его комнате горит свет и сидят агенты.
export function usePresence(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    const ping = () => { api("/presence/ping", { method: "POST" }).catch(() => undefined); };
    ping();
    const t = setInterval(ping, 15_000);
    return () => clearInterval(t);
  }, [enabled]);
}
