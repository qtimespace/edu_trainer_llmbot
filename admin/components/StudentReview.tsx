"use client";
// Работа ученика глазами преподавателя: переписка целиком, команды в терминале, разбор задания (apps/api/review.py).
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Badge, Button, Card, Empty, ErrorBox, Loading, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { ATTENTION, type AttentionLog, ago, duration, focusShare } from "@/lib/attention";
import type { BoardTask } from "@/lib/board";
import { useApi } from "@/lib/hooks";
import { type Analysis, type ChatItem, type ConsoleItem, type Inspect, REVIEW_TABS, TAB_LABEL, clock, dayBreaks,
  failedCount, prompt, studentHref } from "@/lib/review";

type TaskPick = Pick<BoardTask, "id" | "number" | "title">;

// Куда смотрит вкладка ученика: сейчас, итоги с начала дня и лента переходов
export function AttentionCard({ studentId }: { studentId: string }) {
  const [since] = useState(() => { const d = new Date(); d.setHours(0, 0, 0, 0); return d.toISOString(); });
  const { data } = useApi<AttentionLog>(`/group/students/${studentId}/attention?since=${encodeURIComponent(since)}`,
    { pollMs: 5000 });
  const [open, setOpen] = useState(false);
  if (!data) return null;
  const now = Date.now(), share = focusShare(data.totals), cur = ATTENTION[data.state];
  const events = [...data.events].reverse();
  return (
    <Card className="mb-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className={`font-medium ${cur.text}`}>
          <span className={`mr-1.5 inline-block h-2.5 w-2.5 rounded-full ${cur.dot}`} />
          {cur.label}{data.state !== "focused" && data.since ? ` · ${ago(data.since, now)}` : ""}</span>
        <span className="text-zinc-500">сегодня:</span>
        {(["focused", "blurred", "hidden"] as const).map((s) => (
          <span key={s} className={ATTENTION[s].text}>{ATTENTION[s].label} {duration(data.totals[s])}</span>))}
        {share !== null && <Badge tone={share >= 80 ? "green" : share >= 50 ? "yellow" : "red"}>в фокусе {share}%</Badge>}
        {events.length > 0 && <button className="ml-auto text-xs text-indigo-600 hover:underline"
          onClick={() => setOpen(!open)}>{open ? "скрыть ленту" : `лента (${events.length})`}</button>}
      </div>
      {open && <ul className="mt-2 max-h-60 overflow-y-auto border-t border-zinc-100 pt-2 text-xs dark:border-zinc-800">
        {events.map((e, i) => (
          <li key={i} className={ATTENTION[e.state].text}>
            <span className="mr-2 font-mono text-zinc-500">{new Date(e.at).toLocaleTimeString("ru")}</span>
            {ATTENTION[e.state].label}</li>
        ))}
      </ul>}
    </Card>
  );
}

// Вход на страницу ученика сразу в нужную вкладку (офис, группа)
export function StudentLinks({ studentId, compact }: { studentId: string; compact?: boolean }) {
  return (
    <div className={`flex flex-wrap ${compact ? "gap-x-2 gap-y-1" : "gap-2"}`}>
      {REVIEW_TABS.map((t) => (
        <Link key={t} href={studentHref(studentId, t)} className={compact
          ? "text-sm text-indigo-600 hover:underline"
          : "rounded-md border border-indigo-200 px-2.5 py-1 text-sm text-indigo-700 hover:bg-indigo-50 dark:border-indigo-800 dark:text-indigo-300 dark:hover:bg-indigo-950"}>
          {TAB_LABEL[t]}</Link>
      ))}
    </div>
  );
}

function TaskSelect({ tasks, value, onChange, all }: { tasks: TaskPick[]; value: string;
  onChange: (id: string) => void; all?: string }) {
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)} className="max-w-md">
      {all && <option value="">{all}</option>}
      {tasks.map((t) => <option key={t.id} value={t.id}>#{t.number} {t.title}</option>)}
    </Select>
  );
}

// Переписка: ученик — слева, агенты — справа, системные — по центру мелко
export function ChatLog({ studentId, tasks }: { studentId: string; tasks: TaskPick[] }) {
  const [task, setTask] = useState("");
  const path = `/group/students/${studentId}/chat` + (task ? `?task_id=${task}` : "");
  const { data, error } = useApi<ChatItem[]>(path, { pollMs: 3000 });
  return (
    <Card title="Переписка ученика с агентами" actions={<TaskSelect tasks={tasks} value={task} onChange={setTask}
      all="Все задания" />}>
      <ErrorBox error={error} />
      {!data ? <Loading /> : data.length === 0 ? <Empty>Переписки пока нет</Empty> : (
        <div className="flex flex-col gap-2">
          {data.map((m, i) => {
            const meta = <div className="mb-0.5 flex flex-wrap gap-1.5 text-[11px] text-zinc-500">
              <span>{new Date(m.at).toLocaleString("ru")}</span>
              {m.author === "agent" && <Badge tone="blue">{m.agent}</Badge>}
              {!task && <span className="truncate">· {m.task_title}</span>}
              {m.model && <span className="font-mono">{m.model}</span>}
              {m.cost_usd != null && <span>${Number(m.cost_usd).toFixed(4)}</span>}
            </div>;
            if (m.author === "system") return (
              <div key={i} className="mx-auto max-w-xl text-center text-xs text-zinc-500">{meta}
                <span className="whitespace-pre-wrap">{m.text}</span></div>);
            const mine = m.author === "student";
            return (
              <div key={i} className={`max-w-[80%] ${mine ? "self-start" : "self-end"}`}>
                {meta}
                <div className={`whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${mine
                  ? "bg-zinc-100 dark:bg-zinc-800" : "bg-indigo-50 dark:bg-indigo-950"}`}>{m.text}</div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

// Команды ученика из истории bash обеих оболочек: вход lobby и сервер lab
export function ConsoleLog({ studentId }: { studentId: string }) {
  const { data, error } = useApi<ConsoleItem[]>(`/group/students/${studentId}/console`, { pollMs: 3000 });
  const end = useRef<HTMLDivElement>(null);
  const count = data?.length ?? 0;
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [count]);
  const breaks = data ? dayBreaks(data) : new Set<number>();
  return (
    <Card title="Команды в терминале" actions={<span className="text-xs text-zinc-500">
      только введённые команды, без вывода · обновляется каждые 3 с</span>}>
      <ErrorBox error={error} />
      {!data ? <Loading /> : data.length === 0 ? <Empty>Ученик ещё ничего не вводил</Empty> : (
        <div className="max-h-[70vh] overflow-y-auto rounded-md bg-zinc-950 p-3 font-mono text-xs leading-relaxed text-zinc-100">
          {data.map((c, i) => (
            <div key={i}>
              {breaks.has(i) && c.at > 0 && <div className="mt-2 text-zinc-500">
                — {new Date(c.at * 1000).toLocaleDateString("ru")} —</div>}
              <span className="text-zinc-500">{clock(c.at)} </span>
              <span className={c.where === "lobby" ? "text-amber-400" : "text-emerald-400"}>{prompt(c.where)}</span>{" "}
              <span className="whitespace-pre-wrap break-all">{c.cmd}</span>
            </div>
          ))}
          <div ref={end} />
        </div>
      )}
    </Card>
  );
}

// Разбор задания: проверки с командами и выводом, файлы с пометками, по кнопке — разбор модели
export function TaskReview({ studentId, tasks, task, onTask }: { studentId: string; tasks: TaskPick[]; task: string;
  onTask: (id: string) => void }) {
  const path = task ? `/group/students/${studentId}/tasks/${task}/inspect` : null;
  const seen = useApi<Inspect>(path);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => { setAnalysis(null); setError(null); }, [task]);
  const analyze = () => {
    setBusy(true);
    setError(null);
    api<Analysis>(`/group/students/${studentId}/tasks/${task}/analyze`, { method: "POST" })
      .then(setAnalysis, setError).finally(() => setBusy(false));
  };
  return (
    <div className="space-y-4">
      <Card title="Разбор задания" actions={<div className="flex gap-2">
        <TaskSelect tasks={tasks} value={task} onChange={onTask} all="— выберите задание —" />
        {task && <Button variant="secondary" onClick={seen.reload}>Проверить заново</Button>}</div>}>
        <ErrorBox error={seen.error} />
        {!task ? <Empty>Выберите задание — проверки прогонятся в песочнице ученика прямо сейчас</Empty>
          : !seen.data ? <Loading /> : <>
            <div className="mb-2 text-sm">{failedCount(seen.data) === 0
              ? <Badge tone="green">все проверки проходят</Badge>
              : <Badge tone="red">не проходит проверок: {failedCount(seen.data)} из {seen.data.checks.length}</Badge>}</div>
            <ul className="space-y-2">
              {seen.data.checks.map((c, i) => (
                <li key={i} className="rounded-md border border-zinc-200 p-2 dark:border-zinc-800">
                  <div className={c.passed ? "text-emerald-600" : "text-red-600"}>{c.passed ? "✓" : "✗"} {c.about}</div>
                  <code className="mt-1 block text-xs text-zinc-500">$ {c.cmd}</code>
                  {c.output.trim() && <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-zinc-100 p-1.5 text-xs dark:bg-zinc-900">
                    {c.output}</pre>}
                </li>
              ))}
            </ul>
          </>}
      </Card>
      {task && seen.data && <Card title="Файлы ученика" actions={<span className="text-xs text-zinc-500">
        ~ — сервер lab, /home/lobby — вход (до ssh); скрытые не показаны</span>}>
        {seen.data.files.length === 0 ? <Empty>Папки пустые</Empty> : (
          <ul className="font-mono text-xs leading-relaxed">
            {seen.data.files.map((f) => (
              <li key={f.path} className={f.note ? "text-amber-700 dark:text-amber-400" : ""}>
                {f.path}{f.note && <span className="ml-2 font-sans">← {f.note}</span>}</li>
            ))}
          </ul>
        )}
      </Card>}
      {task && <Card title="Почему не засчитано?" actions={<Button onClick={analyze} disabled={busy}>
        {busy ? "Модель разбирает…" : analysis ? "Разобрать ещё раз" : "Разобрать"}</Button>}>
        <ErrorBox error={error} />
        {analysis ? <>
          <div className="whitespace-pre-wrap text-sm">{analysis.text}</div>
          <div className="mt-2 text-xs text-zinc-500">
            <span className="font-mono">{analysis.model}</span> · ${analysis.cost_usd.toFixed(4)} · ученик этот разбор не видит</div>
        </> : <Empty>Методист посмотрит задание, проверки, файлы и команды ученика и напишет вам, где ошибка и что
          подсказать. Это вызов модели за счёт вашего ключа (в бюджет ученика не идёт).</Empty>}
      </Card>}
    </div>
  );
}
