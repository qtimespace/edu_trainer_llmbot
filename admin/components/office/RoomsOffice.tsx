"use client";
import { useEffect, useRef, useState } from "react";
import { type Office, roomGrid, type RoomAgent } from "@/lib/rooms";
import { ROOM_W, RoomCanvas } from "./RoomCanvas";

// Комнаты группы сеткой; масштаб — по ширине контейнера.
export function RoomsOffice({ office, onAgent, selected, onRoom }: { office: Office;
  onAgent?: (studentId: string, a: RoomAgent) => void; selected?: string | null; onRoom?: (studentId: string) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(2);
  const [reduced, setReduced] = useState(false);
  const grid = roomGrid(Math.max(1, office.rooms.length));

  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    const el = wrap.current;
    if (!el) return;
    const fit = () => setScale(Math.max(1, Math.min(4, Math.floor(el.clientWidth / (grid.cols * (ROOM_W + 8))))));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [grid.cols]);

  return (
    <div ref={wrap} className="w-full">
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${grid.cols}, max-content)` }}>
        {office.rooms.map((room) => (
          <div key={room.seat} onClick={() => room.student && onRoom?.(room.student.id)}
            className={`rounded-lg p-1 ${room.student && onRoom ? "cursor-pointer" : ""} ${
              selected && room.student?.id === selected ? "ring-2 ring-indigo-500" : ""}`}>
            <RoomCanvas room={room} scale={scale} reduced={reduced}
              onAgent={room.student ? (a) => onAgent?.(room.student!.id, a) : undefined} />
          </div>
        ))}
      </div>
    </div>
  );
}
