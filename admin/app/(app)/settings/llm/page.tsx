"use client";
import { useState } from "react";
import { Badge, Button, Card, ErrorBox, Field, FormRow, Input, Loading, PageTitle, Select, Table } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { modelBody, modelKey, type Offer, PROVIDERS, type Provider } from "@/lib/llm";

type Model = { key: string; provider: string; model: string; context_window: number;
  pricing: { input: number; output: number }; enabled: boolean };
type Overview = { keys: Record<Provider, boolean>; models: Model[] };

function KeyRow({ provider, set, onChange }: { provider: Provider; set: boolean; onChange: () => void }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState<Error | null>(null);
  return (
    <tr>
      <td className="font-medium">{PROVIDERS[provider]}</td>
      <td>{set ? <Badge tone="green">задан</Badge> : <Badge>не задан</Badge>}</td>
      <td><FormRow>
        <Input className="w-80" type="password" placeholder="новый ключ" value={key} onChange={(e) => setKey(e.target.value)} />
        <Button disabled={key.length < 8} onClick={() => api(`/settings/llm/keys/${provider}`, { method: "PUT",
          body: { key } }).then(() => { setKey(""); setError(null); onChange(); }, setError)}>Сохранить</Button>
        {set && <Button variant="ghost" onClick={() => api(`/settings/llm/keys/${provider}`, { method: "DELETE" })
          .then(onChange, setError)}>Удалить</Button>}
      </FormRow><ErrorBox error={error} /></td>
    </tr>
  );
}

function AddModel({ keys, onChange }: { keys: Record<Provider, boolean>; onChange: () => void }) {
  const [provider, setProvider] = useState<Provider>(keys.openrouter ? "openrouter" : "hf");
  const [offers, setOffers] = useState<Offer[] | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<Error | null>(null);
  const load = () => api<Offer[]>(`/settings/llm/offers/${provider}`).then(setOffers, setError);
  const add = (o: Offer) => api(`/settings/llm/models/${modelKey(provider, o.model)}`, { method: "PUT",
    body: modelBody(provider, o) }).then(onChange, setError);
  const shown = (offers ?? []).filter((o) => o.model.toLowerCase().includes(filter.toLowerCase())).slice(0, 50);
  return (
    <Card title="Добавить модель из списка провайдера" className="mt-4">
      <ErrorBox error={error} />
      <FormRow>
        <Field label="Провайдер" className="w-48"><Select value={provider} onChange={(e) => {
          setProvider(e.target.value as Provider); setOffers(null); }}>
          {(Object.keys(PROVIDERS) as Provider[]).map((p) => <option key={p} value={p}>{PROVIDERS[p]}</option>)}
        </Select></Field>
        <Button disabled={!keys[provider]} onClick={load}>Загрузить список</Button>
        {offers && <Field label="Поиск" className="w-64"><Input value={filter} onChange={(e) => setFilter(e.target.value)}
          placeholder="qwen, llama, deepseek…" /></Field>}
      </FormRow>
      {offers && <Table head={["Модель", "Окно", "Цена за 1M (вход/выход)", ""]}>
        {shown.map((o) => <tr key={o.model}><td className="font-mono text-xs">{o.model}</td>
          <td>{o.context_window ?? "?"}</td>
          <td>{o.pricing ? `$${o.pricing.input} / $${o.pricing.output}` : "нет цены"}</td>
          <td><Button variant="secondary" disabled={!o.pricing || !o.context_window} onClick={() => add(o)}>Добавить</Button></td>
        </tr>)}
      </Table>}
    </Card>
  );
}

export default function LlmSettingsPage() {
  const { data, error, reload } = useApi<Overview>("/settings/llm");
  const [err, setErr] = useState<Error | null>(null);
  if (!data) return <><ErrorBox error={error} /><Loading /></>;
  return (
    <>
      <PageTitle>Модели и ключи</PageTitle>
      <Card title="Ключи провайдеров" className="mb-4">
        <p className="mb-2 text-zinc-500">Ключи хранятся зашифрованными и никому не показываются — даже вам.</p>
        <Table head={["Провайдер", "Ключ", ""]}>
          {(Object.keys(PROVIDERS) as Provider[]).map((p) => <KeyRow key={p} provider={p} set={data.keys[p]} onChange={reload} />)}
        </Table>
      </Card>
      <Card title="Модели в каталоге">
        <ErrorBox error={err} />
        <Table head={["Ключ", "Модель", "Цена за 1M", ""]}>
          {data.models.map((m) => <tr key={m.key}><td className="font-mono text-xs">{m.key}</td>
            <td className="font-mono text-xs">{m.model}</td><td>${m.pricing.input} / ${m.pricing.output}</td>
            <td><Button variant="ghost" onClick={() => api(`/settings/llm/models/${m.key}`, { method: "DELETE" })
              .then(reload, setErr)}>Удалить</Button></td></tr>)}
        </Table>
      </Card>
      <AddModel keys={data.keys} onChange={reload} />
    </>
  );
}
