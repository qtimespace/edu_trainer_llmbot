"use client";
import Link from "next/link";
import { RoomsOffice } from "@/components/office/RoomsOffice";
import { Badge, Card, Empty, ErrorBox, Loading, PageTitle } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import type { Office } from "@/lib/rooms";
import { statusLabel, type StudentTask } from "@/lib/tasks";

const TONE = { todo: "gray", in_progress: "blue", waiting_student: "yellow", done: "green", draft: "gray" } as const;

export default function RoomPage() {
  const office = useApi<Office>("/office", { pollMs: 2000 });
  const tasks = useApi<StudentTask[]>("/me/tasks", { pollMs: 5000 });
  if (!office.data || !tasks.data) return <><ErrorBox error={office.error ?? tasks.error} /><Loading /></>;
  return (
    <>
      <PageTitle>Моя комната</PageTitle>
      <div className="flex flex-col gap-4 lg:flex-row">
        <Card title="Мои задания" className="lg:w-80">
          {tasks.data.length === 0 && <Empty>Заданий пока нет — подожди преподавателя</Empty>}
          <ol className="space-y-2">
            {tasks.data.map((t) => (
              <li key={t.id}><Link href={`/room/tasks/${t.id}`} className="block rounded border border-zinc-200 p-2
                hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800">
                <div className="font-medium">{t.title}</div>
                <Badge tone={TONE[t.status]}>{statusLabel(t.status)}</Badge></Link></li>
            ))}
          </ol>
        </Card>
        <div className="min-w-0 flex-1"><RoomsOffice office={office.data} /></div>
      </div>
    </>
  );
}
