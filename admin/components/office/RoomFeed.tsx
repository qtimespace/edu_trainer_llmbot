"use client";
import { Badge, Card, Empty } from "@/components/ui";
import { useApi } from "@/lib/hooks";

type FeedItem = { at: string; author: "agent" | "system"; agent: string | null; task_title: string; text: string;
  model: string | null; cost_usd: number | null; checks: { about: string; passed: boolean }[] };

// Окно «ответы LLM» по комнате ученика (только преподаватель).
export function RoomFeed({ studentId, name }: { studentId: string; name: string }) {
  const { data } = useApi<FeedItem[]>(`/office/rooms/${studentId}/feed`, { pollMs: 3000 });
  return (
    <Card title={`Ответы LLM — ${name}`} className="max-h-[80vh] overflow-y-auto">
      {!data?.length && <Empty>Агенты ещё ничего не ответили</Empty>}
      {data?.map((m, i) => (
        <div key={i} className="mb-3 border-b border-zinc-100 pb-2 dark:border-zinc-800">
          <div className="mb-1 flex flex-wrap items-center gap-1 text-xs text-zinc-500">
            <span>{new Date(m.at).toLocaleTimeString("ru")}</span>
            <Badge tone={m.author === "system" ? "red" : "blue"}>{m.author === "system" ? "система" : m.agent}</Badge>
            <span className="truncate">{m.task_title}</span>
            {m.model && <span className="font-mono">{m.model}</span>}
            {m.cost_usd != null && <span>${Number(m.cost_usd).toFixed(4)}</span>}
          </div>
          <div className="whitespace-pre-wrap">{m.text}</div>
          {m.checks.length > 0 && <div className="mt-1 text-xs">
            {m.checks.map((c, j) => <div key={j} className={c.passed ? "text-emerald-600" : "text-red-600"}>
              {c.passed ? "✓" : "✗"} {c.about}</div>)}</div>}
        </div>
      ))}
    </Card>
  );
}
