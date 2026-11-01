// Фронт-офис (спека 2026-10-20-front-office): раскладка, палитры и кадры персонажей — без canvas, проверяется тестами.
export type AgentState = "typing" | "reading" | "waiting" | "blocked" | "error" | "done" | "seated" | "idle";
export type OfficeAgent = { key: string; stage: string; model: string; state: AgentState;
  last: { outcome: string; detail: string; at: string } | null };
export type OfficeDesk = { kind: string; kind_label: string; id: string; iid: string; title: string; status: string;
  mine: boolean; url: string; spent_usd: number; budget_usd: number; final: boolean;
  waiting: { reason: string; url: string } | null; blocked: { icon: string; reason: string } | null;
  agents: OfficeAgent[] };
export type OfficeData = { desks: OfficeDesk[]; idle: string[]; now: string;
  roster?: { key: string; name: string; kind: string }[];
  summary: { desks: number; waiting: number; working: number; blocked: number } };

export type Point = { x: number; y: number };
export type DeskPlace = { box: { x: number; y: number; w: number; h: number }; seats: Point[]; desk: OfficeDesk;
  agents: OfficeAgent[] };
export type Layout = { cols: number; rows: number; walkable: boolean[][]; desks: DeskPlace[]; lounge: Point[];
  plants: Point[] };

export const TILE = 16;
export const SEATS = 8; // мест за столом: команды до 8 участников, больше — второй стол того же запуска
const CLUSTER_W = SEATS + 2;
const CLUSTER_H = 4; // ряд мест, стол, два ряда прохода
const PER_ROW = 2;
const LOUNGE_W = 7;

// Столы — сетка по два в ряд; справа — комната отдыха, где бродят свободные агенты.
export function buildLayout(desks: OfficeDesk[]): Layout {
  const places: { desk: OfficeDesk; agents: OfficeAgent[] }[] = [];
  for (const d of desks) {
    for (let i = 0; i < Math.max(1, Math.ceil(d.agents.length / SEATS)); i++) {
      places.push({ desk: d, agents: d.agents.slice(i * SEATS, (i + 1) * SEATS) });
    }
  }
  const clusterRows = Math.max(2, Math.ceil(places.length / PER_ROW));
  const cols = 1 + PER_ROW * CLUSTER_W + LOUNGE_W + 1;
  const rows = 2 + clusterRows * CLUSTER_H + 1;
  const walkable = Array.from({ length: rows }, (_, y) =>
    Array.from({ length: cols }, (_, x) => y > 1 && y < rows - 1 && x > 0 && x < cols - 1));
  const result: DeskPlace[] = [];
  places.forEach((p, i) => {
    const bx = 1 + (i % PER_ROW) * CLUSTER_W;
    const by = 2 + Math.floor(i / PER_ROW) * CLUSTER_H;
    const seats = p.agents.map((_, s) => ({ x: bx + 1 + s, y: by }));
    for (let x = bx + 1; x < bx + 1 + SEATS; x++) walkable[by + 1][x] = false; // стол
    for (const s of seats) walkable[s.y][s.x] = false; // занятые стулья
    result.push({ box: { x: bx, y: by, w: CLUSTER_W, h: CLUSTER_H }, seats, desk: p.desk, agents: p.agents });
  });
  const lx = 1 + PER_ROW * CLUSTER_W;
  const lounge: Point[] = [];
  for (let y = 3; y < rows - 2; y += 2) for (let x = lx + 1; x < cols - 2; x += 2) lounge.push({ x, y });
  const plants = [{ x: lx, y: 2 }, { x: cols - 2, y: 2 }, { x: cols - 2, y: rows - 2 }];
  for (const p of plants) walkable[p.y][p.x] = false;
  return { cols, rows, walkable, desks: result, lounge: lounge.filter((p) => walkable[p.y][p.x]), plants };
}

// Внешность агента — по хэшу ключа: стабильна между обновлениями и различима у соседей.
export function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}
const SKINS = ["#f1c27d", "#e0ac69", "#c68642", "#8d5524", "#ffdbac"];
const HAIRS = ["#2b1d0e", "#5a3825", "#b55239", "#d6b370", "#1c1c1c", "#7a7a7a"];
export function palette(key: string) {
  const h = hash(key);
  return { skin: SKINS[h % SKINS.length], hair: HAIRS[(h >>> 3) % HAIRS.length],
    shirt: `hsl(${(h >>> 6) % 360} 60% 50%)`, pants: `hsl(${(h >>> 15) % 360} 25% 30%)` };
}

export type Frame = "sit" | "type1" | "type2" | "read1" | "read2" | "walk1" | "walk2" | "stand";
export function frameFor(state: AgentState, ms: number, reduced = false): Frame {
  if (reduced) return state === "idle" ? "stand" : "sit";
  if (state === "typing") return Math.floor(ms / 250) % 2 ? "type2" : "type1";
  if (state === "reading") return Math.floor(ms / 600) % 2 ? "read2" : "read1";
  if (state === "idle") return Math.floor(ms / 300) % 2 ? "walk2" : "walk1";
  return "sit";
}

export function bubbleFor(state: AgentState): { icon: string; tone: string; label: string } | null {
  if (state === "waiting") return { icon: "?", tone: "#f59e0b", label: "ждёт человека" };
  if (state === "error") return { icon: "!", tone: "#dc2626", label: "ошибка" };
  if (state === "done") return { icon: "✓", tone: "#16a34a", label: "сделал" };
  return null;
}

export const STATE_LABEL: Record<AgentState, string> = { typing: "пишет", reading: "проверяет", waiting: "ждёт вас",
  blocked: "остановлен", error: "ошибка", done: "сделал", seated: "ждёт своей стадии", idle: "свободен" };

export const deskKey = (d: OfficeDesk) => `${d.kind}:${d.id}`;

// Столы, которые начали ждать человека после прошлого опроса; prev = null — первая загрузка, звонить не о чем.
export function newlyWaiting(prev: Set<string> | null, desks: OfficeDesk[]): string[] {
  if (prev === null) return [];
  return desks.filter((d) => d.waiting && !prev.has(deskKey(d))).map(deskKey);
}

// Путь по сетке (BFS, 4 направления): null — не дойти.
export function bfs(grid: boolean[][], from: Point, to: Point): Point[] | null {
  const rows = grid.length, cols = grid[0]?.length ?? 0;
  if (!grid[to.y]?.[to.x]) return null;
  const prev = new Map<string, string | null>([[`${from.x},${from.y}`, null]]);
  const queue: Point[] = [from];
  while (queue.length) {
    const cur = queue.shift()!;
    if (cur.x === to.x && cur.y === to.y) {
      const path: Point[] = [];
      for (let k: string | null = `${cur.x},${cur.y}`; k; k = prev.get(k) ?? null) {
        const [x, y] = k.split(",").map(Number);
        path.unshift({ x, y });
      }
      return path;
    }
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const n = { x: cur.x + dx, y: cur.y + dy };
      const k = `${n.x},${n.y}`;
      if (n.x < 0 || n.y < 0 || n.x >= cols || n.y >= rows || !grid[n.y][n.x] || prev.has(k)) continue;
      prev.set(k, `${cur.x},${cur.y}`);
      queue.push(n);
    }
  }
  return null;
}
