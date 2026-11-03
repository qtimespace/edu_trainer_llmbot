"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { RoomFeed } from "@/components/office/RoomFeed";
import { TaskBoard } from "@/components/TaskBoard";
import { Card, Empty, ErrorBox, Loading, PageTitle } from "@/components/ui";
import { api } from "@/lib/api";
import type { Board } from "@/lib/board";
import { useApi } from "@/lib/hooks";

type Student = { account_id: string; name: string };

// Доска ученика глазами преподавателя: можно перенести карточку в любой этап (кроме «К выполнению»)
export default function StudentBoardPage() {
  const { id } = useParams<{ id: string }>();
  const board = useApi<Board>(`/group/students/${id}/board`, { pollMs: 3000 });
  const group = useApi<{ students: Student[] }>("/group");
  const [error, setError] = useState<Error | null>(null);
  const name = group.data?.students.find((s) => s.account_id === id)?.name ?? "";
  if (!board.data) return <><ErrorBox error={board.error} /><Loading /></>;
  return (
    <>
      <PageTitle actions={<Link href="/group" className="text-sm text-indigo-600 hover:underline">← Группа</Link>}>
        Доска: {name}</PageTitle>
      <ErrorBox error={error} />
      <Card className="mb-4">
        {board.data.tasks.length === 0 ? <Empty>У ученика нет одобренных заданий</Empty>
          : <TaskBoard board={board.data} teacher onMove={(t, stage) =>
            api(`/group/students/${id}/tasks/${t.id}/move`, { method: "POST", body: { stage } })
              .then(() => setError(null), setError).finally(board.reload)} />}
      </Card>
      {name && <RoomFeed studentId={id} name={name} />}
    </>
  );
}
