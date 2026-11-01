// Изометрический офис (спека 2026-10-21-office-isometric): проекция, раскладка отделов и зоны отдыха, реплики,
// внешность агента — чистая логика без canvas, проверяется тестами.
import { hash, type OfficeAgent, type OfficeDesk, palette, type Point } from "./office";

export const TW = 32; // ширина ромба клетки при масштабе 1
export const TH = 16;

export type Origin = { ox: number; oy: number };
// верхняя вершина ромба клетки
export const toScreen = (x: number, y: number, o: Origin): Point =>
  ({ x: (x - y) * (TW / 2) + o.ox, y: (x + y) * (TH / 2) + o.oy });

export function toGrid(sx: number, sy: number, o: Origin): Point {
  const a = (sx - o.ox) / (TW / 2), b = (sy - o.oy) / (TH / 2);
  return { x: Math.floor((a + b) / 2), y: Math.floor((b - a) / 2) };
}

// дальние клетки раньше; на одной клетке — пол, потом то, что над ним
export function depthOrder<T extends { x: number; y: number; layer: number }>(items: T[]): T[] {
  return [...items].sort((p, q) => p.x + p.y - (q.x + q.y) || p.layer - q.layer || p.x - q.x);
}

// куда смотрит сидящий: S — +y, N — −y (посадка «y»); W — −x, E — +x (посадка «x», как в Game Dev Story)
export type Facing = "N" | "S" | "W" | "E";
export type Seating = "x" | "y";
export type Seat = { x: number; y: number; facing: Facing; monitor: Point };
// offset — номер первого места островка в составе запуска: один агент бывает в команде несколько раз (разные модели)
export type Island = { desk: OfficeDesk; offset: number; agents: OfficeAgent[]; seats: Seat[]; deskCells: Point[]; plaque: Point;
  aisle: Point };
export type FurnitureKind = "sofa" | "table" | "vending" | "cooler" | "shelf" | "plant" | "aquarium" | "whiteboard"
  | "reception" | "cabinet" | "leaddesk" | "leadchair" | "partition";
export type Composition = "classic" | "zones";
export type Furniture = { kind: FurnitureKind; x: number; y: number; facing?: Facing };
export type IsoLayout = { cols: number; rows: number; lx: number; walkable: boolean[][]; islands: Island[]; furniture: Furniture[];
  lounge: Point[]; sofaSeats: Seat[] };

const PER_SIDE = 4; // мест с одной стороны островка
const SEATS = PER_SIDE * 2;
const CW = 6, CH = 6; // отдел: островок 4×2 стола, кресла по обе стороны, проходы вокруг
const PER_ROW = 2;
const LW = 8; // зона отдыха справа

// Отделы — сеткой по два; справа — зона отдыха. Стены — строка y=0 и столбец x=0.
export function buildIsoLayout(desks: OfficeDesk[], seating: Seating = "y", composition: Composition = "classic"): IsoLayout {
  const places: { desk: OfficeDesk; offset: number; agents: OfficeAgent[] }[] = [];
  for (const d of desks) {
    for (let i = 0; i < Math.max(1, Math.ceil(d.agents.length / SEATS)); i++) {
      places.push({ desk: d, offset: i * SEATS, agents: d.agents.slice(i * SEATS, (i + 1) * SEATS) });
    }
  }
  const clusterRows = Math.max(2, Math.ceil(places.length / PER_ROW));
  const lx = 1 + PER_ROW * CW;
  const cols = lx + LW;
  const rows = 1 + clusterRows * CH;
  const walkable = Array.from({ length: rows }, (_, y) => Array.from({ length: cols }, (_, x) => x > 0 && y > 0));
  const block = (p: Point) => { walkable[p.y][p.x] = false; };

  const islands: Island[] = places.map((p, i) => {
    const cx = 1 + (i % PER_ROW) * CW, cy = 1 + Math.floor(i / PER_ROW) * CH;
    const deskCells: Point[] = [];
    if (seating === "x") { // 2 стола по x × 4 по y «спина к спине»; ближний ряд (x+4) смотрит на −x, дальний (x+1) — на +x
      for (let dy = 1; dy <= PER_SIDE; dy++) deskCells.push({ x: cx + 2, y: cy + dy }, { x: cx + 3, y: cy + dy });
      const seats: Seat[] = p.agents.map((_, s) => s < PER_SIDE
        ? { x: cx + 4, y: cy + 1 + s, facing: "W" as const, monitor: { x: cx + 3, y: cy + 1 + s } }
        : { x: cx + 1, y: cy + 1 + s - PER_SIDE, facing: "E" as const, monitor: { x: cx + 2, y: cy + 1 + s - PER_SIDE } });
      const plaque = { x: cx + 2, y: cy + 5 };
      [...deskCells, ...seats, plaque].forEach(block);
      return { desk: p.desk, offset: p.offset, agents: p.agents, seats, deskCells, plaque, aisle: { x: cx, y: cy } };
    }
    for (let dx = 1; dx <= PER_SIDE; dx++) deskCells.push({ x: cx + dx, y: cy + 2 }, { x: cx + dx, y: cy + 3 });
    const seats: Seat[] = p.agents.map((_, s) => s < PER_SIDE
      ? { x: cx + 1 + s, y: cy + 1, facing: "S" as const, monitor: { x: cx + 1 + s, y: cy + 2 } }
      : { x: cx + 1 + s - PER_SIDE, y: cy + 4, facing: "N" as const, monitor: { x: cx + 1 + s - PER_SIDE, y: cy + 3 } });
    const plaque = { x: cx + 5, y: cy + 2 };
    [...deskCells, ...seats, plaque].forEach(block);
    return { desk: p.desk, offset: p.offset, agents: p.agents, seats, deskCells, plaque, aisle: { x: cx, y: cy + 1 } };
  });

  const furniture: Furniture[] = composition === "zones" ? zoneFurniture(lx, rows) : [
    { kind: "whiteboard", x: 4, y: 0 },
    { kind: "plant", x: lx, y: 1 }, { kind: "shelf", x: lx + 3, y: 1 }, { kind: "cooler", x: lx + 5, y: 1 },
    { kind: "vending", x: lx + 6, y: 1 }, { kind: "plant", x: lx + 7, y: 4 },
    { kind: "sofa", x: lx + 2, y: 5, facing: "S" }, { kind: "sofa", x: lx + 3, y: 5, facing: "S" },
    { kind: "table", x: lx + 2, y: 6 }, { kind: "table", x: lx + 3, y: 6 },
    { kind: "sofa", x: lx + 2, y: 7, facing: "N" }, { kind: "sofa", x: lx + 3, y: 7, facing: "N" },
    { kind: "aquarium", x: lx + 6, y: 9 }, { kind: "plant", x: lx, y: rows - 1 },
  ];
  furniture.filter((f) => f.y > 0).forEach(block);
  const sofaSeats: Seat[] = furniture.filter((f) => f.kind === "sofa").map((f) =>
    ({ x: f.x, y: f.y, facing: f.facing ?? "S", monitor: { x: f.x, y: f.y + (f.facing === "N" ? -1 : 1) } }));
  const lounge: Point[] = [];
  for (let y = 2; y < rows; y += 2) for (let x = lx; x < cols; x += 2) if (walkable[y][x]) lounge.push({ x, y });
  return { cols, rows, lx, walkable, islands, furniture, lounge, sofaSeats };
}

// Зоны комнаты (арт-дирекшен §6) в правой части: у окна в дальнем углу — автомат, кулер, растения; стол руководителя с
// доской у задней стены; скамьи со стеклянным столом и стеллаж у правой стены; низкая перегородка с проходом; лобби у
// края — ресепшен буквой Г, низкие шкафы с папками и аквариум торцом ряда.
function zoneFurniture(lx: number, rows: number): Furniture[] {
  const front = rows - 1;
  return [
    { kind: "whiteboard", x: lx + 2, y: 0 }, { kind: "whiteboard", x: 4, y: 0 },
    { kind: "plant", x: lx, y: 1 }, { kind: "leadchair", x: lx + 3, y: 1, facing: "S" },
    { kind: "cooler", x: lx + 5, y: 1 }, { kind: "vending", x: lx + 6, y: 1 }, { kind: "plant", x: lx + 7, y: 1 },
    { kind: "leaddesk", x: lx + 2, y: 2 }, { kind: "leaddesk", x: lx + 3, y: 2 },
    { kind: "sofa", x: lx + 5, y: 4, facing: "S" }, { kind: "sofa", x: lx + 6, y: 4, facing: "S" },
    { kind: "table", x: lx + 5, y: 5 }, { kind: "table", x: lx + 6, y: 5 },
    { kind: "sofa", x: lx + 5, y: 6, facing: "N" }, { kind: "sofa", x: lx + 6, y: 6, facing: "N" },
    { kind: "shelf", x: lx + 7, y: 4 }, { kind: "plant", x: lx + 7, y: 7 },
    { kind: "partition", x: lx, y: front - 4 }, { kind: "partition", x: lx + 1, y: front - 4 },
    { kind: "partition", x: lx + 2, y: front - 4 }, { kind: "partition", x: lx + 3, y: front - 4 },
    { kind: "reception", x: lx + 2, y: front - 2 }, { kind: "reception", x: lx + 3, y: front - 2 },
    { kind: "reception", x: lx + 4, y: front - 2 }, { kind: "reception", x: lx + 4, y: front - 1 },
    { kind: "cabinet", x: lx + 1, y: front }, { kind: "cabinet", x: lx + 2, y: front }, { kind: "cabinet", x: lx + 3, y: front },
    { kind: "aquarium", x: lx + 7, y: front }, { kind: "plant", x: lx + 6, y: front },
  ];
}

// --- реплики (спека §«Реплики») ------------------------------------------------------------------------------------
export type Reply = { text: string; tone: string; sticky: boolean; priority: number; href?: string };
const OCCASIONAL = 5; // печатающий/читающий говорит примерно раз в 5 окон по 4 с

export function replyFor(a: OfficeAgent, d: OfficeDesk, nowMs: number): Reply | null {
  if (a.state === "waiting") {
    return { text: "Нужен ответ!", tone: "#f59e0b", sticky: true, priority: 0, href: d.waiting?.url ?? d.url };
  }
  if (a.state === "error") {
    const detail = a.last?.detail ?? "";
    const text = /429|rate.?limit/i.test(detail) ? "429, жду…"
      : /бюджет|budget/i.test(detail) ? "Кончился бюджет" : "Ошибка!";
    return { text, tone: "#dc2626", sticky: false, priority: 1 };
  }
  if (a.state === "done") return { text: "Готово!", tone: "#16a34a", sticky: false, priority: 2 };
  if (d.status === "waiting_docs" && d.agents[0]?.key === a.key) {
    return { text: "Ждём документы", tone: "#64748b", sticky: false, priority: 1 };
  }
  if ((a.state === "typing" || a.state === "reading")
    && (Math.floor(nowMs / 4000) + hash(a.key)) % OCCASIONAL === 0) {
    return { text: a.state === "typing" ? "Пишу…" : "Проверяю…", tone: "#475569", sticky: false, priority: 3 };
  }
  return null;
}

// все ждущие + не больше трёх остальных, важные (ошибки) раньше
export function pickReplies<T extends { reply: Reply }>(items: T[], limit = 3): T[] {
  const sticky = items.filter((i) => i.reply.sticky);
  const rest = items.filter((i) => !i.reply.sticky).sort((p, q) => p.reply.priority - q.reply.priority).slice(0, limit);
  return [...sticky, ...rest];
}

// --- внешность ----------------------------------------------------------------------------------------------------
export type Look = ReturnType<typeof palette> & { hairStyle: number; outfit: "shirt" | "jacket" | "hoodie";
  accessory: "none" | "glasses" | "headset" };
export const HAIR_STYLES = 6;

export function look(key: string): Look {
  const h = hash(key);
  return { ...palette(key), hairStyle: h % HAIR_STYLES, outfit: (["shirt", "jacket", "hoodie"] as const)[(h >>> 4) % 3],
    accessory: (["none", "glasses", "headset"] as const)[(h >>> 9) % 3] };
}

// раскладка пересобирается при смене состава отделов (и замене участника при том же числе), а не на каждом опросе
export const layoutShape = (desks: OfficeDesk[]) =>
  desks.map((d) => `${d.kind}:${d.id}:${d.agents.map((a) => a.key).join(",")}`).join("|");

// подпись таблички — под стойкой, на полу: не закрывает лица сидящих
export function plaqueLabelAt(island: Island, o: Origin): Point {
  const s = toScreen(island.plaque.x, island.plaque.y, o);
  return { x: s.x, y: s.y + TH };
}

// место в запуске — по номеру, не по ключу агента (ключ в составе может повторяться)
export const seatId = (island: Island, seat: number) => `${island.desk.kind}:${island.desk.id}:${island.offset + seat}`;

// --- стол у каждого агента (решение пользователя 2026-10-22) -------------------------------------------------------
// Отделы — по виду агента; место закреплено за агентом (порядок по ключу). Агент запуска без карточки — «гость».
export type RosterAgent = { key: string; name: string; kind: string };
const DEPTS: { id: string; label: string; kinds: string[] }[] = [
  { id: "authors", label: "Аналитики и писатели", kinds: ["author"] },
  { id: "checkers", label: "Проверяющие", kinds: ["verifier"] },
  { id: "owners", label: "Сервисы", kinds: ["owner"] },
  { id: "lead", label: "Руководство", kinds: ["orchestrator"] },
  { id: "guests", label: "Гости", kinds: [] },
];

export function buildRosterLayout(roster: RosterAgent[], guests: string[], seating: Seating = "y",
  composition: Composition = "zones"): IsoLayout {
  const known = new Set(DEPTS.flatMap((d) => d.kinds));
  const members = (d: (typeof DEPTS)[number]) => d.id === "guests" ? guests.map((key) => ({ key, name: key, kind: "guest" }))
    : roster.filter((a) => d.kinds.includes(a.kind) || (d.id === "authors" && !known.has(a.kind)));
  const pseudo: OfficeDesk[] = DEPTS.map((d) => ({ d, list: members(d) })).filter(({ list }) => list.length).map(({ d, list }) => ({
    kind: "dept", kind_label: d.label, id: d.id, iid: "", title: d.label, status: "", mine: false, url: "", spent_usd: 0,
    budget_usd: 0, final: false, waiting: null, blocked: null,
    agents: [...list].sort((p, q) => p.key.localeCompare(q.key))
      .map((a) => ({ key: a.key, stage: "", model: "", state: "idle" as const, last: null })),
  }));
  return buildIsoLayout(pseudo, seating, composition);
}

// Состояние агента по всем запускам: важнейшее (ждёт человека → ошибка → печатает → проверяет → готово → …)
const RANK: Record<string, number> = { waiting: 0, error: 1, typing: 2, reading: 3, done: 4, blocked: 5, seated: 6, idle: 7 };
export type AgentStatus = { agent: OfficeAgent; desk: OfficeDesk; runs: OfficeDesk[] };

export function agentStatus(desks: OfficeDesk[]): Map<string, AgentStatus> {
  const out = new Map<string, AgentStatus>();
  for (const d of desks) for (const a of d.agents) {
    if (d.final && a.state !== "done" && a.state !== "error") continue; // завершённый запуск — только свежий итог
    const cur = out.get(a.key);
    if (!cur) { out.set(a.key, { agent: a, desk: d, runs: [d] }); continue; }
    if (!cur.runs.includes(d)) cur.runs.push(d);
    if ((RANK[a.state] ?? 9) < (RANK[cur.agent.state] ?? 9)) { cur.agent = a; cur.desk = d; }
  }
  for (const s of out.values()) s.runs = [s.desk, ...s.runs.filter((r) => r !== s.desk)];
  return out;
}

// раскладка зависит только от состава отделов, не от состояний
export const rosterShape = (roster: RosterAgent[], guests: string[]) =>
  [...roster.map((a) => `${a.kind}:${a.key}`), ...guests.map((g) => `guest:${g}`)].join("|");
