"use client";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef, useState } from "react";
import { Card, ErrorBox } from "@/components/ui";
import { api } from "@/lib/api";
import { decodeChunk, parseSize, type Screen } from "@/lib/screen";

const POLL_MS = 2000;

// Экран терминала ученика глазами преподавателя: тот же вывод (команды и ответы, nano, сессия на lab), что видел
// ученик, — только чтение; новое подгружается раз в 2 с. Размер — как у окна ученика.
export function TerminalScreen({ studentId }: { studentId: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<Error | null>(null);
  const [empty, setEmpty] = useState(true);

  useEffect(() => {
    let disposed = false, timer: ReturnType<typeof setTimeout> | undefined;
    let cleanup = () => undefined as void;
    (async () => {
      const { Terminal: XTerm } = await import("@xterm/xterm");
      if (disposed || !host.current) return;
      const term = new XTerm({ disableStdin: true, cursorBlink: false, fontSize: 13, cols: 80, rows: 24,
        scrollback: 5000, fontFamily: "ui-monospace, Menlo, Consolas, monospace", theme: { background: "#0b0f14" } });
      term.open(host.current);
      cleanup = () => term.dispose();
      let last = 0;
      const poll = async () => {
        try {
          const s = await api<Screen>(`/group/students/${studentId}/terminal?after=${last}`);
          if (disposed) return;
          for (const c of s.chunks) {
            if (c.kind === "size") {
              const size = parseSize(c.data);
              if (size) term.resize(size.cols, size.rows);
            } else {
              term.write(decodeChunk(c.data));
            }
          }
          if (s.chunks.some((c) => c.kind === "out")) setEmpty(false);
          last = s.last;
          setError(null);
        } catch (e) {
          if (!disposed) setError(e as Error);
        }
        if (!disposed) timer = setTimeout(poll, POLL_MS);
      };
      await poll();
    })();
    return () => { disposed = true; if (timer) clearTimeout(timer); cleanup(); };
  }, [studentId]);

  return (
    <Card title="Экран терминала" className="mb-4" actions={<span className="text-xs text-zinc-500">
      как видел ученик: команды и ответы · только просмотр · обновляется каждые 2 с</span>}>
      <ErrorBox error={error} />
      {empty && <p className="mb-2 text-sm text-zinc-500">Пока пусто — запись идёт с момента выкладки этой функции,
        когда ученик открывает терминал.</p>}
      <div className="overflow-x-auto rounded-md bg-[#0b0f14] p-1"><div ref={host} className="inline-block" /></div>
    </Card>
  );
}
