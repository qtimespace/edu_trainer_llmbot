"use client";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/tasks";

// Терминал песочницы ученика: xterm ↔ WebSocket /ws/terminal (бинарные кадры; ресайз — JSON).
export function Terminal({ generation = 0 }: { generation?: number }) {
  const host = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"connecting" | "open" | "closed">("connecting");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    let cleanup = () => undefined as void;
    (async () => {
      const [{ Terminal: XTerm }, { FitAddon }] = await Promise.all([import("@xterm/xterm"), import("@xterm/addon-fit")]);
      if (disposed || !host.current) return;
      const term = new XTerm({ cursorBlink: true, fontSize: 14, fontFamily: "ui-monospace, Menlo, Consolas, monospace",
        theme: { background: "#0b0f14" } });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(host.current);
      fit.fit();
      const ws = new WebSocket(wsUrl(window.location, process.env.NEXT_PUBLIC_WS_URL));
      ws.binaryType = "arraybuffer";
      const enc = new TextEncoder();
      const sendSize = () => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      };
      ws.onopen = () => { setState("open"); sendSize(); term.focus(); };
      ws.onmessage = (e) => term.write(typeof e.data === "string" ? e.data : new Uint8Array(e.data as ArrayBuffer));
      ws.onclose = () => { setState("closed"); term.write("\r\n\x1b[33m[соединение закрыто]\x1b[0m\r\n"); };
      const input = term.onData((d) => { if (ws.readyState === WebSocket.OPEN) ws.send(enc.encode(d)); });
      const ro = new ResizeObserver(() => { fit.fit(); sendSize(); });
      ro.observe(host.current);
      cleanup = () => { ro.disconnect(); input.dispose(); ws.close(); term.dispose(); };
    })();
    return () => { disposed = true; cleanup(); };
  }, [attempt, generation]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between rounded-t bg-zinc-800 px-2 py-1 text-xs text-zinc-300">
        <span>Терминал {state === "open" ? "· подключён" : state === "connecting" ? "· подключаюсь…" : "· отключён"}</span>
        {state === "closed" && <button className="underline" onClick={() => { setState("connecting"); setAttempt((n) => n + 1); }}>
          Переподключиться</button>}
      </div>
      <div ref={host} className="min-h-[360px] flex-1 rounded-b bg-[#0b0f14] p-1" />
    </div>
  );
}
