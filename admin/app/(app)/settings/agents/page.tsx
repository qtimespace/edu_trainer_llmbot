"use client";
import { useState } from "react";
import { Badge, Button, Card, ErrorBox, Field, FormRow, Input, Loading, PageTitle, Select, Textarea }
  from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

type Agent = { key: string; name: string; kind: "methodist" | "tutor"; system_prompt: string; route: string[];
  max_usd_per_call: number; enabled: boolean };
type Overview = { models: { key: string }[] };

function AgentEditor({ agent, models, onChange }: { agent: Agent; models: string[]; onChange: () => void }) {
  const [a, setA] = useState(agent);
  const [error, setError] = useState<Error | null>(null);
  const [saved, setSaved] = useState(false);
  const save = () => api(`/agents/${a.key}`, { method: "PUT", body: { ...a, key: undefined } })
    .then(() => { setSaved(true); setError(null); onChange(); }, setError);
  return (
    <Card className="mb-4" title={<>{a.name} <span className="font-mono text-xs text-zinc-500">{a.key}</span>{" "}
      <Badge tone={a.kind === "methodist" ? "blue" : "green"}>{a.kind === "methodist" ? "методист" : "тьютор"}</Badge>
      {!a.enabled && <> <Badge>выключен</Badge></>}</>}
      actions={<Button onClick={save}>{saved ? "Сохранено" : "Сохранить"}</Button>}>
      <ErrorBox error={error} />
      <FormRow>
        <Field label="Имя" className="w-48"><Input value={a.name} onChange={(e) => { setSaved(false);
          setA({ ...a, name: e.target.value }); }} /></Field>
        <Field label="Лимит на один ответ, $" className="w-40"><Input value={a.max_usd_per_call}
          onChange={(e) => { setSaved(false); setA({ ...a, max_usd_per_call: Number(e.target.value) }); }} /></Field>
        <Field label="Модель" className="w-80" hint="Пусто — любая модель каталога">
          <Select value={a.route[0] ?? ""} onChange={(e) => { setSaved(false);
            setA({ ...a, route: e.target.value ? [e.target.value] : [] }); }}>
            <option value="">любая</option>
            {models.map((m) => <option key={m} value={m}>{m}</option>)}</Select></Field>
        <Field label="Включён" className="w-24"><input type="checkbox" checked={a.enabled}
          onChange={(e) => { setSaved(false); setA({ ...a, enabled: e.target.checked }); }} /></Field>
      </FormRow>
      <Field label="Инструкция агента (системный промпт)">
        <Textarea rows={10} value={a.system_prompt} onChange={(e) => { setSaved(false);
          setA({ ...a, system_prompt: e.target.value }); }} /></Field>
    </Card>
  );
}

export default function AgentsPage() {
  const agents = useApi<Agent[]>("/agents");
  const llm = useApi<Overview>("/settings/llm");
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<Error | null>(null);
  if (!agents.data || !llm.data) return <><ErrorBox error={agents.error ?? llm.error} /><Loading /></>;
  const models = llm.data.models.map((m) => m.key);
  const devops = agents.data.find((a) => a.key === "devops");
  return (
    <>
      <PageTitle>Агенты</PageTitle>
      {agents.data.map((a) => <AgentEditor key={a.key} agent={a} models={models} onChange={agents.reload} />)}
      <Card title="Новый агент-тьютор">
        <ErrorBox error={error} />
        <FormRow>
          <Field label="Ключ (латиница)" className="w-48"><Input value={key} onChange={(e) => setKey(e.target.value)}
            placeholder="pythonist" /></Field>
          <Field label="Имя" className="w-48"><Input value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Питонист" /></Field>
          <Button disabled={!key || !name} onClick={() => api(`/agents/${key}`, { method: "PUT", body: {
            name, kind: "tutor", system_prompt: devops?.system_prompt ?? "", route: [], max_usd_per_call: 0.05,
            enabled: true } }).then(() => { setKey(""); setName(""); setError(null); agents.reload(); }, setError)}>
            Создать</Button>
        </FormRow>
      </Card>
    </>
  );
}
