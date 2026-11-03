"use client";
import Link from "next/link";
import { useState } from "react";
import { type Board, type BoardTask, columns, dot, initials, targets } from "@/lib/board";

const AVATAR = ["bg-indigo-500", "bg-sky-600", "bg-emerald-600", "bg-amber-600", "bg-rose-500", "bg-violet-600",
  "bg-teal-600", "bg-fuchsia-600"];
const avatarColor = (key: string) => AVATAR[[...key].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) % AVATAR.length];

// Доска заданий по этапам флоу (образец — доска задач admin_panel): колонки со счётчиком, карточки переносятся мышью
// или меню «Перенести»; разрешённые колонки подсвечиваются во время переноса.
export function TaskBoard({ board, teacher = false, hrefFor, onMove }: { board: Board; teacher?: boolean;
  hrefFor?: (t: BoardTask) => string; onMove: (task: BoardTask, stage: string) => Promise<unknown> }) {
  const [drag, setDrag] = useState<BoardTask | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const allowed = drag ? targets(board, drag.stage, teacher) : [];
  const move = async (t: BoardTask, stage: string) => {
    setBusy(t.id);
    try { await onMove(t, stage); } finally { setBusy(null); }
  };
  const names = Object.fromEntries(board.stages.map((s) => [s.key, s.name]));

  return (
    <div className="flex gap-3 overflow-x-auto pb-3">
      {columns(board).map(({ stage, tasks }) => {
        const open = allowed.includes(stage.key);
        return (
          <section key={stage.key} aria-label={stage.name}
            className={`flex w-64 shrink-0 flex-col rounded-lg bg-zinc-100 p-2 transition dark:bg-zinc-900 ${
              drag ? (open ? "ring-2 ring-indigo-400" : "opacity-60") : ""}`}
            onDragOver={(e) => { if (open) e.preventDefault(); }}
            onDrop={(e) => { e.preventDefault(); if (drag && open) void move(drag, stage.key); setDrag(null); }}>
            <header className="mb-2 flex items-center justify-between px-1">
              <div>
                <div className="font-medium">{stage.name}</div>
                {stage.agent && <div className="text-xs text-zinc-500">ведёт: {stage.agent.name}</div>}
              </div>
              <span className="rounded bg-zinc-300 px-1.5 text-xs font-semibold text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200">
                {tasks.length}</span>
            </header>
            <div className="flex min-h-16 flex-col gap-2">
              {tasks.map((t) => {
                const d = dot(t), to = targets(board, t.stage, teacher);
                const title = <span className="block text-sm leading-snug">{t.title}</span>;
                return (
                  <article key={t.id} draggable={to.length > 0 && busy === null}
                    onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; setDrag(t); }}
                    onDragEnd={() => setDrag(null)}
                    className={`rounded-md border border-zinc-200 bg-white p-2 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 ${
                      to.length ? "cursor-grab active:cursor-grabbing" : ""} ${busy === t.id ? "opacity-50" : ""}`}>
                    <div className="mb-1 flex items-center gap-1.5 text-xs text-zinc-500">
                      <span className={`inline-block h-2.5 w-2.5 rounded-full ${d.color}`} title={d.label} />
                      <span>#{t.number}</span>
                      <span className="truncate">· {d.label}</span>
                      <span title={t.agent.name} aria-label={`ведёт ${t.agent.name}`}
                        className={`ml-auto inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-semibold text-white ${avatarColor(t.agent.key)}`}>
                        {initials(t.agent.name)}</span>
                    </div>
                    {hrefFor ? <Link href={hrefFor(t)} className="hover:text-indigo-600 hover:underline">{title}</Link> : title}
                    <div className="mt-1.5 flex items-center gap-1">
                      {t.lesson && <span className="truncate rounded bg-sky-100 px-1.5 text-[11px] text-sky-800 dark:bg-sky-950 dark:text-sky-200">
                        {t.lesson}</span>}
                      {to.length > 0 && (
                        <select aria-label={`Перенести «${t.title}»`} value="" disabled={busy !== null}
                          className="ml-auto max-w-28 rounded border border-zinc-200 bg-transparent text-[11px] text-zinc-500 dark:border-zinc-700"
                          onChange={(e) => e.target.value && void move(t, e.target.value)}>
                          <option value="">Перенести…</option>
                          {to.map((k) => <option key={k} value={k}>{names[k]}</option>)}
                        </select>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
