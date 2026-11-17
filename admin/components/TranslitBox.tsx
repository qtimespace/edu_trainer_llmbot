"use client";
import { useState } from "react";
import { Button, ErrorBox, Textarea } from "@/components/ui";
import { api } from "@/lib/api";

// Нет русской раскладки: ученик пишет транслитом (privet, fajl), агент переводит в кириллицу — дальше текст можно
// скопировать в терминал (Ctrl+V) или отправить агенту. Перевод — вызов модели за счёт бюджета ученика.
export function TranslitBox({ taskId, onUse }: { taskId: string; onUse?: (text: string) => void }) {
  const [open, setOpen] = useState(false);
  const [src, setSrc] = useState("");
  const [out, setOut] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  if (!open) return (
    <button type="button" className="px-3 pt-2 text-left text-xs text-indigo-600 hover:underline"
      onClick={() => setOpen(true)}>⌨ Нет русской раскладки? Напиши транслитом — переведу в русские буквы</button>);
  const convert = () => {
    setBusy(true);
    setCopied(false);
    api<{ text: string }>(`/me/tasks/${taskId}/translit`, { method: "POST", body: { text: src } })
      .then((r) => { setOut(r.text); setError(null); }, setError).finally(() => setBusy(false));
  };
  const copy = () => navigator.clipboard?.writeText(out).then(() => setCopied(true), () => setCopied(false));
  return (
    <div className="space-y-2 border-t border-zinc-200 p-3 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between text-xs text-zinc-500">
        <span>Транслит → русский: privet → привет, fajl → файл. Имена файлов и команды не меняются.</span>
        <button type="button" className="hover:underline" onClick={() => setOpen(false)}>скрыть</button>
      </div>
      <div className="flex gap-2">
        <Textarea rows={2} className="flex-1 font-sans text-sm" value={src} placeholder="Napishi tut translitom…"
          onChange={(e) => setSrc(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (src.trim() && !busy) convert(); } }} />
        <Button type="button" variant="secondary" disabled={busy || !src.trim()} onClick={convert}>
          {busy ? "Перевожу…" : "Перевести"}</Button>
      </div>
      <ErrorBox error={error} />
      {out && <div className="rounded bg-zinc-100 p-2 dark:bg-zinc-800">
        <div className="whitespace-pre-wrap">{out}</div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button type="button" variant="secondary" onClick={copy}>{copied ? "Скопировано ✓" : "Копировать"}</Button>
          {onUse && <Button type="button" variant="secondary" onClick={() => onUse(out)}>В ответ агенту</Button>}
          <span className="text-xs text-zinc-500">в терминал — щёлкни в нём и нажми Ctrl+V</span>
        </div>
      </div>}
    </div>
  );
}
