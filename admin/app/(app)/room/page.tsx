"use client";
import { useState } from "react";
import { RoomsOffice } from "@/components/office/RoomsOffice";
import { TaskBoard } from "@/components/TaskBoard";
import { Card, Empty, ErrorBox, Loading, PageTitle } from "@/components/ui";
import { api } from "@/lib/api";
import type { Board } from "@/lib/board";
import { useApi } from "@/lib/hooks";
import type { Office } from "@/lib/rooms";

export default function RoomPage() {
  const office = useApi<Office>("/office", { pollMs: 2000 });
  const board = useApi<Board>("/me/board", { pollMs: 3000 });
  const [error, setError] = useState<Error | null>(null);
  if (!board.data) return <><ErrorBox error={board.error} /><Loading /></>;
  return (
    <>
      <PageTitle>Моя комната</PageTitle>
      <ErrorBox error={error} />
      <Card title="Мои задания" className="mb-4">
        {board.data.tasks.length === 0 ? <Empty>Заданий пока нет — подожди преподавателя</Empty> : <>
          <p className="mb-2 text-xs text-zinc-500">Перетащи карточку на следующий этап — задание подхватит агент этого
            этапа. В «Готово» карточка попадёт, только когда пройдут все проверки.</p>
          <TaskBoard board={board.data} hrefFor={(t) => `/room/tasks/${t.id}`} onMove={(t, stage) =>
            api(`/me/tasks/${t.id}/move`, { method: "POST", body: { stage } }).then(() => setError(null), setError)
              .finally(board.reload)} />
        </>}
      </Card>
      {office.data && <RoomsOffice office={office.data} />}
    </>
  );
}
