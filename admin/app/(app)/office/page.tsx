"use client";
import { useState } from "react";
import { RoomFeed } from "@/components/office/RoomFeed";
import { RoomsOffice } from "@/components/office/RoomsOffice";
import { Badge, Card, ErrorBox, Loading, Modal, PageTitle } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { type Office, type RoomAgent, STATE_LABEL } from "@/lib/rooms";

export default function OfficePage() {
  const { data, error } = useApi<Office>("/office", { pollMs: 2000 });
  const [room, setRoom] = useState<string | null>(null);
  const [agent, setAgent] = useState<RoomAgent | null>(null);
  if (!data) return <><ErrorBox error={error} /><Loading /></>;
  if (data.size === 0) return <><PageTitle>Офис</PageTitle><Card>Сначала создайте группу.</Card></>;
  const selected = data.rooms.find((r) => r.student?.id === room)?.student ?? null;
  const online = data.rooms.filter((r) => r.online).length;
  return (
    <>
      <PageTitle actions={<Badge tone={online ? "green" : "gray"}>в сети {online} из {
        data.rooms.filter((r) => r.student).length}</Badge>}>Офис</PageTitle>
      <ErrorBox error={error} />
      <div className="flex flex-col gap-4 xl:flex-row">
        <div className="min-w-0 flex-1">
          <RoomsOffice office={data} selected={room} onRoom={setRoom}
            onAgent={(sid, a) => { setRoom(sid); setAgent(a); }} />
          <p className="mt-2 text-xs text-zinc-500">Нажмите на комнату, чтобы видеть ответы LLM, или на агента — что он делает.</p>
        </div>
        <div className="xl:w-96">{selected ? <RoomFeed key={selected.id} studentId={selected.id} name={selected.name} />
          : <Card><span className="text-zinc-500">Выберите комнату</span></Card>}</div>
      </div>
      <Modal open={agent !== null} title={agent?.name ?? ""} onClose={() => setAgent(null)}>
        {agent && <>
          <p className="mb-2"><Badge tone="blue">{STATE_LABEL[agent.state]}</Badge></p>
          <p className="mb-2">Задание: {agent.task ? `${agent.task.title} (${agent.task.status})` : "—"}</p>
          {agent.last_reply && <><div className="text-xs text-zinc-500">Последний ответ:</div>
            <p className="whitespace-pre-wrap">{agent.last_reply}</p></>}
        </>}
      </Modal>
    </>
  );
}
