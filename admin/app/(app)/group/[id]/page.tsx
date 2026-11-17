"use client";
import Link from "next/link";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { RoomFeed } from "@/components/office/RoomFeed";
import { ChatLog, ConsoleLog, TaskReview } from "@/components/StudentReview";
import { TaskBoard } from "@/components/TaskBoard";
import { Card, Empty, ErrorBox, Loading, PageTitle, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import type { Board } from "@/lib/board";
import { useApi } from "@/lib/hooks";
import { type ReviewTab, reviewTab } from "@/lib/review";

type Student = { account_id: string; name: string };

// Ученик глазами преподавателя: доска (перенос в любой этап, кроме «К выполнению»), переписка, команды в терминале
// и разбор задания. Вкладка и задание — в адресе (?tab=review&task=…): ссылку можно открыть заново.
function StudentPage() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = reviewTab(params.get("tab"));
  const task = params.get("task") ?? "";
  const go = (next: { tab?: ReviewTab; task?: string }) => {
    const q = new URLSearchParams({ tab: next.tab ?? tab, ...((next.task ?? task) ? { task: next.task ?? task } : {}) });
    router.replace(`${pathname}?${q}`, { scroll: false });
  };
  const board = useApi<Board>(`/group/students/${id}/board`, { pollMs: 3000 });
  const group = useApi<{ students: Student[] }>("/group");
  const [error, setError] = useState<Error | null>(null);
  const name = group.data?.students.find((s) => s.account_id === id)?.name ?? "";
  if (!board.data) return <><ErrorBox error={board.error} /><Loading /></>;
  const tasks = [...board.data.tasks].sort((a, b) => a.number - b.number);
  return (
    <>
      <PageTitle actions={<Link href="/group" className="text-sm text-indigo-600 hover:underline">← Группа</Link>}>
        {name || "Ученик"}</PageTitle>
      <Tabs<ReviewTab> value={tab} onChange={(t) => go({ tab: t })} tabs={[
        { key: "board", label: "Доска" }, { key: "chat", label: "Чат" }, { key: "console", label: "Консоль" },
        { key: "review", label: "Разбор задания" }]} />
      {tab === "board" && <>
        <ErrorBox error={error} />
        <Card className="mb-4">
          {tasks.length === 0 ? <Empty>У ученика нет одобренных заданий</Empty>
            : <TaskBoard board={board.data} teacher hrefFor={(t) => `${pathname}?tab=review&task=${t.id}`}
              onMove={(t, stage) => api(`/group/students/${id}/tasks/${t.id}/move`, { method: "POST", body: { stage } })
                .then(() => setError(null), setError).finally(board.reload)} />}
        </Card>
        {name && <RoomFeed studentId={id} name={name} />}
      </>}
      {tab === "chat" && <ChatLog studentId={id} tasks={tasks} />}
      {tab === "console" && <ConsoleLog studentId={id} />}
      {tab === "review" && <TaskReview studentId={id} tasks={tasks} task={task} onTask={(t) => go({ task: t })} />}
    </>
  );
}

export default function StudentBoardPage() {
  return <Suspense fallback={<Loading />}><StudentPage /></Suspense>;
}
