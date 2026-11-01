"use client";
import { useState } from "react";
import { Badge, Button, Card, ErrorBox, Field, FormRow, Input, Loading, Modal, PageTitle, Select, Table, Textarea }
  from "@/components/ui";
import { api } from "@/lib/api";
import { type Group, seatsView, sizeOptions, type Student } from "@/lib/group";
import { useApi } from "@/lib/hooks";

type GroupResp = { group: Group | null; students: Student[] };

function CreateGroup({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [size, setSize] = useState(3);
  const [error, setError] = useState<Error | null>(null);
  return (
    <Card title="Создать группу">
      <ErrorBox error={error} />
      <FormRow>
        <Field label="Название" className="w-64"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Учеников (комнат)" className="w-40">
          <Select value={size} onChange={(e) => setSize(Number(e.target.value))}>
            {sizeOptions().map((n) => <option key={n} value={n}>{n}</option>)}</Select></Field>
        <Button disabled={!name} onClick={() => api("/group", { method: "POST", body: { name, size } })
          .then(onDone, setError)}>Создать</Button>
      </FormRow>
    </Card>
  );
}

function StudentRow({ s, onChange }: { s: Student; onChange: () => void }) {
  const { data: box, reload } = useApi<{ status: string }>(`/group/students/${s.account_id}/sandbox`);
  const [edit, setEdit] = useState(false);
  const [note, setNote] = useState(s.note);
  const [budget, setBudget] = useState(String(s.budget_usd));
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const reset = async () => {
    if (!confirm(`Пересоздать сервер ученика ${s.name}? Все его файлы будут удалены.`)) return;
    await api(`/group/students/${s.account_id}/sandbox/reset`, { method: "POST" }).catch(setError);
    reload();
  };
  return (
    <tr>
      <td>{s.seat}</td>
      <td><div className="font-medium">{s.name}</div><div className="text-xs text-zinc-500">{s.login}</div></td>
      <td className="max-w-xs whitespace-pre-wrap text-xs">{s.note || "—"}</td>
      <td><code>{s.lesson_password}</code></td>
      <td>${s.budget_usd.toFixed(2)}</td>
      <td><Badge tone={box?.status === "running" ? "green" : "gray"}>{box?.status === "running" ? "работает"
        : box?.status === "stopped" ? "остановлен" : "не создан"}</Badge></td>
      <td className="whitespace-nowrap">
        <Button variant="ghost" onClick={() => setEdit(true)}>Изменить</Button>
        <Button variant="ghost" onClick={reset}>Пересоздать сервер</Button>
        <Button variant="ghost" onClick={() => api<{ password: string }>(`/group/students/${s.account_id}/password`,
          { method: "POST" }).then((r) => setSecret(r.password), setError)}>Новый пароль</Button>
        <ErrorBox error={error} />
        <Modal open={edit} title={s.name} onClose={() => setEdit(false)}>
          <Field label="Заметка об ученике (её читает методист)" hint="Уровень, опыт, на что обратить внимание">
            <Textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
          <Field label="Лимит расходов на LLM, $"><Input value={budget} onChange={(e) => setBudget(e.target.value)} /></Field>
          <Button onClick={() => api(`/group/students/${s.account_id}`, { method: "PUT",
            body: { note, budget_usd: Number(budget) } }).then(() => { setEdit(false); onChange(); }, setError)}>
            Сохранить</Button>
        </Modal>
        <Modal open={secret !== null} title="Новый пароль входа" onClose={() => setSecret(null)}>
          <p className="mb-2">Передайте ученику — пароль показывается один раз:</p>
          <code className="text-lg">{secret}</code>
        </Modal>
      </td>
    </tr>
  );
}

function AddStudent({ onDone }: { onDone: () => void }) {
  const [login, setLogin] = useState("");
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [created, setCreated] = useState<{ login: string; password: string } | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const add = () => api<{ student: Student; password: string }>("/group/students", { method: "POST",
    body: { login, name, note } }).then((r) => {
    setCreated({ login: r.student.login, password: r.password });
    setLogin(""); setName(""); setNote(""); setError(null);
    onDone();
  }, setError);
  return (
    <Card title="Добавить ученика" className="mt-4">
      <ErrorBox error={error} />
      <FormRow>
        <Field label="Логин (латиница)" className="w-48"><Input value={login} onChange={(e) => setLogin(e.target.value)} /></Field>
        <Field label="Имя" className="w-48"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Заметка" className="w-96"><Input value={note} onChange={(e) => setNote(e.target.value)}
          placeholder="например: никогда не видел терминал" /></Field>
        <Button disabled={!login || !name} onClick={add}>Добавить</Button>
      </FormRow>
      {created && <p className="rounded bg-emerald-50 p-3 dark:bg-emerald-950">
        Ученик <b>{created.login}</b>, пароль входа: <code className="text-base">{created.password}</code> —
        передайте ученику, больше он не покажется.</p>}
    </Card>
  );
}

export default function GroupPage() {
  const { data, error, reload } = useApi<GroupResp>("/group");
  const [size, setSize] = useState<number | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  if (!data) return <><ErrorBox error={error} /><Loading /></>;
  if (!data.group) return <><PageTitle>Группа</PageTitle><CreateGroup onDone={reload} /></>;
  const group = data.group;
  return (
    <>
      <PageTitle actions={<FormRow>
        <Field label="Учеников (комнат)" className="w-40">
          <Select value={size ?? group.size} onChange={(e) => setSize(Number(e.target.value))}>
            {sizeOptions().map((n) => <option key={n} value={n}>{n}</option>)}</Select></Field>
        {size !== null && size !== group.size && <Button onClick={() => api("/group", { method: "PUT", body: { size } })
          .then(() => { setSize(null); setErr(null); reload(); }, setErr)}>Сохранить</Button>}
      </FormRow>}>Группа «{group.name}»</PageTitle>
      <ErrorBox error={err} />
      <Card>
        <Table head={["Место", "Ученик", "Заметка", "Учебный пароль (ssh)", "Лимит", "Сервер", ""]}>
          {seatsView(group.size, data.students).map(({ seat, student }) => student
            ? <StudentRow key={seat} s={student} onChange={reload} />
            : <tr key={seat}><td>{seat}</td><td colSpan={6} className="text-zinc-400">свободно</td></tr>)}
        </Table>
      </Card>
      {data.students.length < group.size && <AddStudent onDone={reload} />}
    </>
  );
}
