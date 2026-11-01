"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button, ErrorBox, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { canSend, canStart, type Chat } from "@/lib/tasks";

// Чат ученика с агентом по заданию: опрос раз в 2 с, пока агент думает; отправка — когда ход ученика.
export function TaskChat({ taskId, agentName, onStatus }: { taskId: string; agentName: string;
  onStatus?: (s: Chat["status"]) => void }) {
  const { data, error, reload } = useApi<Chat>(`/me/tasks/${taskId}/messages`, { pollMs: 2000 });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<Error | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const count = data?.messages.length ?? 0;
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [count, data?.running]);
  useEffect(() => { if (data) onStatus?.(data.status); }, [data?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return <ErrorBox error={error} />;
  const act = async (path: string, body?: unknown) => {
    setBusy(true);
    try {
      await api(path, { method: "POST", body });
      setText("");
      setErr(null);
    } catch (e) {
      setErr(e as Error);
    } finally {
      setBusy(false);
      reload();
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim() && canSend(data.status, data.running)) act(`/me/tasks/${taskId}/messages`, { text: text.trim() });
  };
  return (
    <div className="flex h-full flex-col rounded border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex-1 space-y-2 overflow-y-auto p-3" style={{ maxHeight: "60vh" }}>
        {data.messages.map((m) => (
          <div key={m.id} className={m.author === "student" ? "ml-8 text-right" : "mr-8"}>
            <div className="text-xs text-zinc-500">{m.author === "student" ? "Ты" : m.author === "agent" ? agentName : "Система"}</div>
            <div className={`inline-block whitespace-pre-wrap rounded-lg px-3 py-2 text-left ${m.author === "student"
              ? "bg-indigo-600 text-white" : m.author === "system" ? "bg-amber-100 text-amber-900" : "bg-zinc-100 dark:bg-zinc-800"}`}>
              {m.text}</div>
            {m.checks.length > 0 && <div className="mt-1 text-xs">{m.checks.map((c, i) =>
              <div key={i} className={c.passed ? "text-emerald-600" : "text-zinc-500"}>{c.passed ? "✓" : "○"} {c.about}</div>)}</div>}
          </div>
        ))}
        {data.running && <div className="text-zinc-500">{agentName} думает и проверяет твой сервер…</div>}
        {data.status === "done" && <div className="rounded bg-emerald-50 p-2 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
          Задание выполнено! 🎉</div>}
        <div ref={end} />
      </div>
      <ErrorBox error={err} />
      {canStart(data.status) ? (
        <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
          <Button className="w-full" disabled={busy} onClick={() => act(`/me/tasks/${taskId}/start`)}>Отправить агенту</Button>
        </div>
      ) : data.status !== "done" && (
        <form onSubmit={submit} className="flex gap-2 border-t border-zinc-200 p-3 dark:border-zinc-800">
          <Textarea rows={2} className="flex-1 font-sans text-sm" value={text} placeholder="Ответ агенту… (Enter — отправить)"
            disabled={!canSend(data.status, data.running)} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }} />
          <Button type="submit" disabled={busy || !text.trim() || !canSend(data.status, data.running)}>Отправить</Button>
        </form>
      )}
    </div>
  );
}
