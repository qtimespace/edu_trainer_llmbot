// Офис группы — один этаж: кабинет преподавателя, коридор и кабинеты учеников по обе стороны коридора. Свет и агенты — только когда ученик в сети (данные — GET /office).
export type AgentState = "typing" | "waiting" | "idle" | "done";
export type RoomAgent = { key: string; name: string; state: AgentState;
  task: { id: string; title: string; status: string } | null; last_reply: string | null };
export type Room = { seat: number; student: { id: string; name: string } | null; online: boolean; lights: boolean;
  agents: RoomAgent[] };
export type Office = { size: number; rooms: Room[] };
export type Cell = { x: number; y: number };

export const ROOM_COLS = 10, ROOM_ROWS = 7, PER_ROW = 6, MAX_DESKS = 2 * PER_ROW;

export type Rect = { x0: number; y0: number; x1: number; y1: number };
// перегородка: axis "x" — по левому краю клетки (x, y), "y" — по верхнему
export type Wall = { x: number; y: number; axis: "x" | "y" };
export type Cabin = { rect: Rect; door: Cell; plant: Cell; back: boolean };
export type OfficePlan = { cols: number; rows: number; teacher: Rect; hall: Rect; cabins: Cabin[]; walls: Wall[] };
export const TEACH_W = 8, HALL = 2, DOOR_AT = 3; // дверь — в проходе между парами столов

// Кабинеты парами (за коридором и перед ним) в ряд от кабинета преподавателя; коридор открыт в его кабинет.
export function officePlan(n: number): OfficePlan {
  const twoRows = n > 1, front = ROOM_ROWS + HALL;
  const cols = TEACH_W + Math.max(1, Math.ceil(n / (twoRows ? 2 : 1))) * ROOM_COLS;
  const rows = twoRows ? front + ROOM_ROWS : front;
  const cabins: Cabin[] = [], walls: Wall[] = [];
  for (let i = 0; i < n; i++) {
    const back = !twoRows || i % 2 === 0, x0 = TEACH_W + (twoRows ? Math.floor(i / 2) : i) * ROOM_COLS;
    const y0 = back ? 0 : front, rect = { x0, y0, x1: x0 + ROOM_COLS, y1: y0 + ROOM_ROWS };
    const door = { x: x0 + DOOR_AT, y: back ? ROOM_ROWS : front };
    for (let y = Math.max(1, y0); y < rect.y1; y++) walls.push({ x: x0, y, axis: "x" });
    for (let x = x0; x < rect.x1; x++) if (x !== door.x) walls.push({ x, y: door.y, axis: "y" });
    cabins.push({ rect, door, plant: { x: rect.x1 - 2, y: y0 + 1 }, back });
  }
  return { cols, rows, teacher: { x0: 0, y0: 0, x1: TEACH_W, y1: rows },
    hall: { x0: TEACH_W, y0: ROOM_ROWS, x1: cols, y1: front }, cabins, walls };
}

export function cabinAt(plan: OfficePlan, c: Cell): number | null {
  const i = plan.cabins.findIndex(({ rect: r }) => c.x >= r.x0 && c.x < r.x1 && c.y >= r.y0 && c.y < r.y1);
  return i < 0 ? null : i;
}

// агент сидит лицом к зрителю, стол — перед ним (на клетку ниже по y)
export function roomLayout(agentCount: number, at: { x0: number; y0: number } = { x0: 0, y0: 0 }): { seats: Cell[]; desks: Cell[] } {
  const n = Math.min(agentCount, MAX_DESKS);
  // столы парами с проходом между парами; два ряда — вся команда агентов в одном кабинете
  const seats = Array.from({ length: n }, (_, i) => {
    const col = i % PER_ROW;
    return { x: at.x0 + 1 + col + Math.floor(col / 2), y: at.y0 + 2 + 2 * Math.floor(i / PER_ROW) };
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
