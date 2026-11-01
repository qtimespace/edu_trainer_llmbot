"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Loading, PageTitle, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Lesson } from "@/lib/lessons";

export default function LessonsPage() {
  const router = useRouter();
  const { data, error } = useApi<Lesson[]>("/lessons");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [err, setErr] = useState<Error | null>(null);
  if (!data) return <><ErrorBox error={error} /><Loading /></>;
  return (
    <>
      <PageTitle>Уроки</PageTitle>
      <Card className="mb-4">
        {data.length === 0 && <Empty>Уроков пока нет</Empty>}
        <ol className="space-y-1">
          {data.map((l) => <li key={l.id}><Link className="text-indigo-600 hover:underline" href={`/lessons/${l.id}`}>
            {l.position}. {l.title}</Link>{" "}
            {l.prep_status === "running" && <Badge tone="blue">готовятся задания</Badge>}
            {l.prep_status === "failed" && <Badge tone="red">ошибка подготовки</Badge>}</li>)}
        </ol>
      </Card>
      <Card title="Новый урок">
        <ErrorBox error={err} />
        <Field label="Тема"><Input value={title} onChange={(e) => setTitle(e.target.value)}
          placeholder="Bash: подключение и файлы" /></Field>
        <Field label="Описание урока" hint="Что ученики должны уметь после урока: команды, понятия, примеры заданий.
          По этому описанию методист подготовит задания под каждого ученика.">
          <Textarea rows={8} className="font-sans text-sm" value={description}
            onChange={(e) => setDescription(e.target.value)} /></Field>
        <Button disabled={!title} onClick={() => api<Lesson>("/lessons", { method: "POST", body: { title, description } })
          .then((l) => router.push(`/lessons/${l.id}`), setErr)}>Создать урок</Button>
      </Card>
    </>
  );
}
