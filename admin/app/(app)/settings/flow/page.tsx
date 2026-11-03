"use client";
import { useState } from "react";
import { Button, Card, ErrorBox, Input, Loading, PageTitle, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { addStage, type Flow, has, moveStage, removeStage, toggle, updateStage } from "@/lib/flow";
import { useApi } from "@/lib/hooks";

type Agent = { key: string; name: string; kind: string; enabled: boolean };
const FIXED = new Set(["todo", "done"]);

export default function FlowPage() {
  const flow = useApi<Flow>("/flow");
  const agents = useApi<Agent[]>("/agents");
  const [draft, setDraft] = useState<Flow | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [saved, setSaved] = useState(false);
  const f = draft ?? flow.data;
  if (!f) return <><ErrorBox error={flow.error} /><Loading /></>;
  const tutors = (agents.data ?? []).filter((a) => a.kind === "tutor" && a.enabled);
  const edit = (next: Flow) => { setDraft(next); setSaved(false); };
  const save = () => api<Flow>("/flow", { method: "PUT", body: f })
    .then(() => { setDraft(null); setError(null); setSaved(true); return flow.reload(); }, setError);
  const from = f.stages.filter((s) => s.key !== "done"), to = f.stages.filter((s) => s.key !== "todo");

  return (
    <>
      <PageTitle actions={<>
        {draft && <Button variant="ghost" onClick={() => setDraft(null)}>Отменить</Button>}
        <Button disabled={!draft} onClick={save}>Сохранить</Button></>}>Флоу заданий</PageTitle>
      <ErrorBox error={error} />
      {saved && <p className="mb-3 text-sm text-emerald-600">Сохранено — доски учеников уже по новому флоу.</p>}
      <p className="mb-4 text-sm text-zinc-500">Этапы — колонки доски ученика. На каждом этапе задание ведёт свой агент;
        «агент задания» — тот, кого выбрал методист. В «Готово» задание попадает, только когда прошли все проверки.</p>
      <Card title="Этапы" className="mb-4" actions={<Button variant="secondary" onClick={() => edit(addStage(f))}>
        + Этап</Button>}>
        <ol className="space-y-2">
          {f.stages.map((s, i) => (
            <li key={s.key} className="flex flex-wrap items-center gap-2">
              <span className="w-6 text-right text-zinc-400">{i + 1}.</span>
              <Input className="w-48" aria-label="Название этапа" value={s.name} maxLength={40}
                onChange={(e) => edit(updateStage(f, s.key, { name: e.target.value }))} />
              {FIXED.has(s.key) ? <span className="text-xs text-zinc-500">{s.key === "todo" ? "задания ещё не начаты"
                : "все проверки прошли"}</span> : <>
                <Select className="w-56" aria-label={`Кто ведёт этап «${s.name}»`} value={s.agent_key ?? ""}
                  onChange={(e) => edit(updateStage(f, s.key, { agent_key: e.target.value || null }))}>
                  <option value="">агент задания</option>
                  {tutors.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
                  {s.agent_key && !tutors.some((a) => a.key === s.agent_key) &&
                    <option value={s.agent_key}>{s.agent_key} (выключен)</option>}
                </Select>
                <Button variant="ghost" aria-label="Выше" onClick={() => edit(moveStage(f, s.key, -1))}>↑</Button>
                <Button variant="ghost" aria-label="Ниже" onClick={() => edit(moveStage(f, s.key, 1))}>↓</Button>
                <Button variant="ghost" onClick={() => edit(removeStage(f, s.key))}>Убрать</Button>
              </>}
            </li>
          ))}
        </ol>
      </Card>
      <Card title="Переходы: куда ученик может перенести карточку">
        <div className="overflow-x-auto">
          <table className="text-sm">
            <thead><tr><th className="p-1 text-left text-xs font-normal text-zinc-500">из ↓ / в →</th>
              {to.map((s) => <th key={s.key} className="p-1 font-medium">{s.name}</th>)}</tr></thead>
            <tbody>
              {from.map((a) => (
                <tr key={a.key} className="border-t border-zinc-100 dark:border-zinc-800">
                  <th className="p-1 text-left font-medium">{a.name}</th>
                  {to.map((b) => <td key={b.key} className="p-1 text-center">
                    {a.key !== b.key && <input type="checkbox" aria-label={`${a.name} → ${b.name}`} checked={has(f, a.key, b.key)}
                      onChange={() => edit(toggle(f, a.key, b.key))} />}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
