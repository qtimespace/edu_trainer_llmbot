"use client";
import { use, useState } from "react";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Loading, PageTitle, Select, Textarea }
  from "@/components/ui";
import { api, isUuid } from "@/lib/api";
import type { Student } from "@/lib/group";
import { useApi } from "@/lib/hooks";
import { canApprove, type Check, groupByStudent, type Lesson, STATUS_LABEL, type TeacherTask } from "@/lib/lessons";

type Agent = { key: string; name: string; kind: string; enabled: boolean };

function TaskEditor({ task, tutors, onChange }: { task: TeacherTask; tutors: Agent[]; onChange: () => void }) {
  const [title, setTitle] = useState(task.title);
  const [statement, setStatement] = useState(task.statement);
  const [checks, setChecks] = useState<Check[]>(task.checks);
  const [agent, setAgent] = useState(task.agent_key);
  const [error, setError] = useState<Error | null>(null);
  const editable = task.status === "draft" || task.status === "todo";
  const dirty = title !== task.title || statement !== task.statement || agent !== task.agent_key
    || JSON.stringify(checks) !== JSON.stringify(task.checks);
  const save = () => api(`/tasks/${task.id}`, { method: "PUT", body: { title, statement, checks, agent_key: agent } })
    .then(onChange, setError);
  return (
    <div className="mb-3 rounded border border-zinc-200 p-3 dark:border-zinc-800">
      <ErrorBox error={error} />
      <div className="mb-2 flex items-center gap-2">
        <Input className="flex-1 font-medium" value={title} disabled={!editable} onChange={(e) => setTitle(e.target.value)} />
        <Select className="w-40" value={agent} disabled={!editable} onChange={(e) => setAgent(e.target.value)}>
          {tutors.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}</Select>
        <Badge tone={task.status === "draft" ? "yellow" : task.status === "done" ? "green" : "blue"}>
          {STATUS_LABEL[task.status]}</Badge>
      </div>
      <Textarea rows={3} className="mb-2 font-sans text-sm" value={statement} disabled={!editable}
        onChange={(e) => setStatement(e.target.value)} />
      <div className="mb-1 text-xs font-medium text-zinc-500">Проверки (команда завершается с кодом 0, если сделано)</div>
      {checks.map((c, i) => (
        <div key={i} className="mb-1 flex gap-2">
          <Input className="flex-1 font-mono text-xs" value={c.cmd} disabled={!editable}
            onChange={(e) => setChecks(checks.map((x, j) => (j === i ? { ...x, cmd: e.target.value } : x)))} />
          <Input className="flex-1" value={c.about} disabled={!editable} placeholder="что проверяется"
            onChange={(e) => setChecks(checks.map((x, j) => (j === i ? { ...x, about: e.target.value } : x)))} />
          {editable && checks.length > 1 && <Button variant="ghost" onClick={() => setChecks(checks.filter((_, j) => j !== i))}>
            ✕</Button>}
        </div>))}
      {editable && <div className="mt-2 flex gap-2">
        <Button variant="secondary" onClick={() => setChecks([...checks, { cmd: "", about: "" }])}>+ проверка</Button>
        {dirty && <Button variant="secondary" onClick={save}>Сохранить</Button>}
        {canApprove(task.status) && !dirty && <Button onClick={() => api(`/tasks/${task.id}/approve`, { method: "POST" })
          .then(onChange, setError)}>Одобрить</Button>}
        {task.status === "draft" && <Button variant="ghost" onClick={() => api(`/tasks/${task.id}`, { method: "DELETE" })
          .then(onChange, setError)}>Удалить</Button>}
      </div>}
    </div>
  );
}

export default function LessonPage({ params }: { params: Promise<{ id: string }> }) {
  const raw = use(params).id;
  // id из адреса — только UUID: иначе «../» в ссылке увёл бы POST (с CSRF-токеном) на другой адрес API
  const id = isUuid(raw) ? raw : "00000000-0000-0000-0000-000000000000";
  const lesson = useApi<Lesson[]>("/lessons", { pollMs: 3000 });
  const tasks = useApi<TeacherTask[]>(`/lessons/${id}/tasks`, { pollMs: 3000 });
  const group = useApi<{ students: Student[] }>("/group");
  const agents = useApi<Agent[]>("/agents");
  const [description, setDescription] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const current = lesson.data?.find((l) => l.id === id);
  if (!current || !tasks.data || !group.data || !agents.data) return <><ErrorBox error={lesson.error} /><Loading /></>;
  const tutors = agents.data.filter((a) => a.kind === "tutor");
  const byStudent = groupByStudent(tasks.data);
  const running = current.prep_status === "running";
  const prepare = (student_id?: string) => api(`/lessons/${id}/prepare`, { method: "POST", body: { student_id } })
    .then(() => { setError(null); lesson.reload(); }, setError);
  const reloadAll = () => { tasks.reload(); lesson.reload(); };
  return (
    <>
      <PageTitle actions={<>
        <Button disabled={running} onClick={() => prepare()}>{running ? "Методист готовит…" : "Подготовить задания всем"}</Button>
        {tasks.data.some((t) => t.status === "draft") && <Button variant="secondary" onClick={() =>
          api(`/lessons/${id}/approve`, { method: "POST", body: {} }).then(reloadAll, setError)}>Одобрить всё</Button>}
      </>}>{current.title}</PageTitle>
      <ErrorBox error={error} />
      {current.prep_status === "failed" && <ErrorBox error={`Подготовка не удалась:\n${current.prep_error}`} />}
      <Card title="Описание урока" className="mb-4" actions={description !== null && description !== current.description
        ? <Button variant="secondary" onClick={() => api(`/lessons/${id}`, { method: "PUT", body: { description } })
          .then(() => { setDescription(null); lesson.reload(); }, setError)}>Сохранить</Button> : null}>
        <Textarea rows={6} className="font-sans text-sm" value={description ?? current.description}
          onChange={(e) => setDescription(e.target.value)} />
      </Card>
      {group.data.students.map((s) => {
        const list = byStudent.get(s.account_id) ?? [];
        return (
          <Card key={s.account_id} className="mb-4" title={<>{s.name} <span className="text-xs font-normal text-zinc-500">
            {s.note}</span></>} actions={<>
            <Button variant="secondary" disabled={running} onClick={() => prepare(s.account_id)}>Подготовить заново</Button>
            {list.some((t) => t.status === "draft") && <Button variant="secondary" onClick={() =>
              api(`/lessons/${id}/approve`, { method: "POST", body: { student_id: s.account_id } })
                .then(reloadAll, setError)}>Одобрить всё ученику</Button>}</>}>
            {list.length === 0 ? <Empty>{running ? "Методист готовит задания…" : "Заданий нет"}</Empty>
              : list.map((t) => <TaskEditor key={`${t.id}-${t.status}`} task={t} tutors={tutors} onChange={reloadAll} />)}
          </Card>
        );
      })}
    </>
  );
}
