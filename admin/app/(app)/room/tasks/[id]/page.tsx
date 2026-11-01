"use client";
import Link from "next/link";
import { use, useState } from "react";
import { TaskChat } from "@/components/TaskChat";
import { Terminal } from "@/components/Terminal";
import { Badge, Button, ErrorBox, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Office } from "@/lib/rooms";
import { statusLabel, type StudentTask } from "@/lib/tasks";

export default function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const task = useApi<StudentTask>(`/me/tasks/${id}`);
  const office = useApi<Office>("/office");
  const [generation, setGeneration] = useState(0);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  if (!task.data) return <><ErrorBox error={task.error} /><Loading /></>;
  const agentName = office.data?.rooms[0]?.agents.find((a) => a.key === task.data!.agent_key)?.name ?? "Агент";
  const reset = async () => {
    if (!confirm("Пересоздать твой сервер? Все файлы на нём удалятся, и всё начнётся с чистого листа.")) return;
    setResetting(true);
    try {
      await api("/me/sandbox/reset", { method: "POST" });
      setGeneration((n) => n + 1);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setResetting(false);
    }
  };
  return (
    <>
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <Link href="/room" className="text-xs text-indigo-600 hover:underline">← к заданиям</Link>
          <h1 className="text-xl font-semibold">{task.data.title} <Badge>{statusLabel(task.data.status)}</Badge></h1>
          <p className="mt-1 max-w-3xl whitespace-pre-wrap">{task.data.statement}</p>
        </div>
        <Button variant="secondary" disabled={resetting} onClick={reset}>
          {resetting ? "Пересоздаю…" : "Пересоздать мой сервер"}</Button>
      </div>
      <ErrorBox error={error} />
      <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
        <Terminal generation={generation} />
        <TaskChat taskId={id} agentName={agentName} onStatus={() => task.reload()} />
      </div>
    </>
  );
}
