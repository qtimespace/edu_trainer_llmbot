// Офис группы: комната на ученика. Свет и агенты — только когда ученик в сети (данные — GET /office).
export type AgentState = "typing" | "waiting" | "idle" | "done";
export type RoomAgent = { key: string; name: string; state: AgentState;
  task: { id: string; title: string; status: string } | null; last_reply: string | null };
export type Room = { seat: number; student: { id: string; name: string } | null; online: boolean; lights: boolean;
  agents: RoomAgent[] };
export type Office = { size: number; rooms: Room[] };
export type Cell = { x: number; y: number };

export const ROOM_COLS = 10, ROOM_ROWS = 7, PER_ROW = 6, MAX_DESKS = 2 * PER_ROW;

export function roomGrid(size: number): { cols: number; rows: number } {
  return size <= 3 ? { cols: Math.max(1, size), rows: 1 } : size === 4 ? { cols: 2, rows: 2 } : { cols: 3, rows: 2 };
}

// агент сидит лицом к зрителю, стол — перед ним (на клетку ниже по y)
export function roomLayout(agentCount: number): { seats: Cell[]; desks: Cell[] } {
  const n = Math.min(agentCount, MAX_DESKS);
  // столы парами с проходом между парами; два ряда — вся команда агентов в одной комнате
  const seats = Array.from({ length: n }, (_, i) => {
    const col = i % PER_ROW;
    return { x: 1 + col + Math.floor(col / 2), y: 2 + 2 * Math.floor(i / PER_ROW) };
  });
  return { seats, desks: seats.map((s) => ({ x: s.x, y: s.y + 1 })) };
}

export const isDark = (room: { online: boolean }) => !room.online;

export function bubbleFor(state: AgentState): string | null {
  return { typing: "…", waiting: "?", done: "✓", idle: null }[state];
}

export const STATE_LABEL: Record<AgentState, string> = {
  typing: "думает и проверяет", waiting: "ждёт ответа ученика", idle: "свободен", done: "задание принято",
};
