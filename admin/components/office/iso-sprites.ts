// Своя пиксельная графика изометрического офиса (спека 2026-10-21-office-isometric): всё рисуется кодом.
// Мебель — изометрические «коробки» с контуром и тремя тонами граней; персонажи — матрицы 16×24 по внешности агента.
import { type ChibiPose, chibiColor, chibiGrid, chibiLook, type ChibiView } from "@/lib/chibi";
import { type Facing, type FurnitureKind, type Look, TH, TW } from "@/lib/iso";

type Ctx = CanvasRenderingContext2D;
type P = [number, number];
const OUTLINE = "#21140c";

// Варианты оформления для выбора пользователем (арт-дирекшен §8): фон вне комнаты, контур, масштаб.
export type Art = { bg: "dark" | "brick"; outline: "silhouette" | "cell"; zoom: "fit" | "x3"; chars: "old" | "chibi";
  seating: "x" | "y"; palette: "old" | "warm"; shadows: boolean; floor: "old" | "carpet" | "plain";
  walls: "old" | "band"; detail: boolean; plaque: "post" | "plate"; composition: "classic" | "zones";
  labels: "always" | "hover"; portrait: "boards" | "simple" | "old" };
export const ART: Art = { bg: "brick", outline: "cell", zoom: "fit", chars: "chibi", seating: "y",
  palette: "warm", shadows: true, floor: "old", walls: "band",
  detail: true, plaque: "plate", composition: "zones", labels: "hover",
  portrait: "boards" }; // шаг 3 — A, шаг 4 — C // выбор пользователя 2026-10-21: шаг 1 — D, шаг 2 — B
export function setArt(a: Partial<Art>) { Object.assign(ART, a); }
export const BG = "#26313d";

// --- примитивы: заливка многоугольника и линия по пикселям, без сглаживания ------------------------------------------
export function fillPoly(ctx: Ctx, pts: P[], color: string) {
  ctx.fillStyle = color;
  const ys = pts.map((p) => p[1]);
  const y0 = Math.floor(Math.min(...ys)), y1 = Math.ceil(Math.max(...ys));
  for (let y = y0; y < y1; y++) {
    const cy = y + 0.5;
    const xs: number[] = [];
    for (let i = 0; i < pts.length; i++) {
      const [ax, ay] = pts[i], [bx, by] = pts[(i + 1) % pts.length];
      if ((ay <= cy && by > cy) || (by <= cy && ay > cy)) xs.push(ax + ((cy - ay) / (by - ay)) * (bx - ax));
    }
    xs.sort((a, b) => a - b);
    for (let i = 0; i + 1 < xs.length; i += 2) {
      const a = Math.round(xs[i]), b = Math.round(xs[i + 1]);
      if (b > a) ctx.fillRect(a, y, b - a, 1);
    }
  }
}

export function line(ctx: Ctx, x0: number, y0: number, x1: number, y1: number, color: string) {
  ctx.fillStyle = color;
  x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1);
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let err = dx + dy;
  for (;;) {
    ctx.fillRect(x0, y0, 1, 1);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}

// точка сетки (дробная, внутри клетки) → экран относительно верхней вершины ромба клетки
const iso = (gx: number, gy: number, h = 0): P => [(gx - gy) * (TW / 2), (gx + gy) * (TH / 2) - h];

type Faces = { top: string; left: string; right: string };
// Коробка на клетке: [x0..x1]×[y0..y1] в долях клетки, высота h; z — подъём над полом. (sx, sy) — вершина ромба.
export function box(ctx: Ctx, sx: number, sy: number, r: { x0: number; x1: number; y0: number; y1: number },
  h: number, f: Faces, z = 0, outline = true) {
  const at = (gx: number, gy: number, hh: number): P => { const [x, y] = iso(gx, gy, hh); return [sx + x, sy + y]; };
  const top: P[] = [at(r.x0, r.y0, z + h), at(r.x1, r.y0, z + h), at(r.x1, r.y1, z + h), at(r.x0, r.y1, z + h)];
  const left: P[] = [at(r.x0, r.y1, z + h), at(r.x1, r.y1, z + h), at(r.x1, r.y1, z), at(r.x0, r.y1, z)];
  const right: P[] = [at(r.x1, r.y0, z + h), at(r.x1, r.y1, z + h), at(r.x1, r.y1, z), at(r.x1, r.y0, z)];
  fillPoly(ctx, left, f.left);
  fillPoly(ctx, right, f.right);
  fillPoly(ctx, top, f.top);
  if (!outline || ART.outline !== "cell") return; // по силуэту — общим проходом слоя предметов
  const edges: [P, P][] = [[top[0], top[1]], [top[1], top[2]], [top[2], top[3]], [top[3], top[0]],
    [left[3], left[2]], [left[2], right[3]], [left[0], left[3]], [top[2], left[2]], [right[0], right[3]]];
  for (const [a, b] of edges) line(ctx, a[0], a[1], b[0], b[1], OUTLINE);
}

// грань «к зрителю слева» (+y): прямоугольник на ней — [u0..u1] вдоль x, [v0..v1] по высоте
export function onLeftFace(ctx: Ctx, sx: number, sy: number, y: number, u0: number, u1: number, v0: number, v1: number,
  color: string) {
  const at = (gx: number, hh: number): P => { const [x, yy] = iso(gx, y, hh); return [sx + x, sy + yy]; };
  fillPoly(ctx, [at(u0, v1), at(u1, v1), at(u1, v0), at(u0, v0)], color);
}
// грань «к зрителю справа» (+x)
export function onRightFace(ctx: Ctx, sx: number, sy: number, x: number, u0: number, u1: number, v0: number,
  v1: number, color: string) {
  const at = (gy: number, hh: number): P => { const [xx, y] = iso(x, gy, hh); return [sx + xx, sy + y]; };
  fillPoly(ctx, [at(u0, v1), at(u1, v1), at(u1, v0), at(u0, v0)], color);
}

// --- пол и стены ------------------------------------------------------------------------------------------------------
export function floorTile(ctx: Ctx, sx: number, sy: number, tone: "wood" | "wood2" | "tile" | "tile2") {
  const c = { wood: "#a8744b", wood2: "#9b6a43", tile: "#b9b6ae", tile2: "#aeaba3" }[tone];
  fillPoly(ctx, [[sx, sy], [sx + TW / 2, sy + TH / 2], [sx, sy + TH], [sx - TW / 2, sy + TH / 2]], c);
  if (tone.startsWith("wood")) line(ctx, sx - TW / 4 + 1, sy + TH / 4 + 1, sx + TW / 4, sy + (3 * TH) / 4, "#8f6140");
}

export const WALL_H = 48;
const WALL: Faces = { top: "#d9d4c8", left: "#ece8de", right: "#d5d0c4" };
// задняя стена вдоль строки y=0 (окно на каждой второй клетке) и вдоль столбца x=0
export function wallBack(ctx: Ctx, sx: number, sy: number, x: number) {
  box(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.72, y1: 1 }, WALL_H, WALL);
  if (x % 2 === 1) {
    onLeftFace(ctx, sx, sy, 1, 0.18, 0.82, 14, 36, "#7fb7e6");
    onLeftFace(ctx, sx, sy, 1, 0.24, 0.42, 18, 32, "#d6ecfb");
    onLeftFace(ctx, sx, sy, 1, 0.18, 0.82, 24, 25, "#5b8fbd");
  }
}
export function wallSide(ctx: Ctx, sx: number, sy: number, y: number) {
  box(ctx, sx, sy, { x0: 0.72, x1: 1, y0: 0, y1: 1 }, WALL_H, WALL);
  if (y % 2 === 1) {
    onRightFace(ctx, sx, sy, 1, 0.18, 0.82, 14, 36, "#7fb7e6");
    onRightFace(ctx, sx, sy, 1, 0.58, 0.76, 18, 32, "#d6ecfb");
  }
}
export function whiteboard(ctx: Ctx, sx: number, sy: number) {
  onLeftFace(ctx, sx, sy, 0.7, 0.08, 0.92, 12, 34, "#f8fafc");
  onLeftFace(ctx, sx, sy, 0.7, 0.2, 0.5, 26, 27, "#dc2626");
  onLeftFace(ctx, sx, sy, 0.7, 0.3, 0.8, 22, 23, "#2563eb");
  onLeftFace(ctx, sx, sy, 0.7, 0.2, 0.62, 18, 19, "#dc2626");
}

// --- пол и стены по арт-дирекшену (§3, §6) ----------------------------------------------------------------------------
const diamond = (sx: number, sy: number): P[] => [[sx, sy], [sx + TW / 2, sy + TH / 2], [sx, sy + TH], [sx - TW / 2, sy + TH / 2]];

// ковёр: основа, 2 светлых пикселя-ромба и 1 тёмный в шахматном порядке; у стен — тёмная полоса 2 px
export function carpetTile(ctx: Ctx, sx: number, sy: number, x: number, y: number, pattern: boolean) {
  fillPoly(ctx, diamond(sx, sy), "#845537");
  if (pattern) {
    const flip = (x + y) % 2 === 0;
    ctx.fillStyle = "#8b603c";
    ctx.fillRect(sx + (flip ? -6 : 4), sy + 6, 2, 1);
    ctx.fillRect(sx + (flip ? 2 : -8), sy + 10, 2, 1);
    ctx.fillStyle = "#72492e";
    ctx.fillRect(sx + (flip ? 6 : -2), sy + 8, 1, 1);
  }
  ctx.fillStyle = "#5a3823";
  if (y === 1) line(ctx, sx, sy, sx + TW / 2, sy + TH / 2, "#5a3823"), line(ctx, sx, sy + 1, sx + TW / 2, sy + TH / 2 + 1, "#5a3823");
  if (x === 1) line(ctx, sx, sy, sx - TW / 2, sy + TH / 2, "#5a3823"), line(ctx, sx, sy + 1, sx - TW / 2, sy + TH / 2 + 1, "#5a3823");
}

// плитка лобби: шахматка 2×2 на клетку со швом
export function lobbyTile(ctx: Ctx, sx: number, sy: number) {
  const q = (gx: number, gy: number): P => [sx + (gx - gy) * (TW / 2), sy + (gx + gy) * (TH / 2)];
  for (const [a, b, c] of [[0, 0, "#9e958a"], [0.5, 0, "#888075"], [0, 0.5, "#888075"], [0.5, 0.5, "#9e958a"]] as const) {
    fillPoly(ctx, [q(a, b), q(a + 0.5, b), q(a + 0.5, b + 0.5), q(a, b + 0.5)], c);
  }
  const [l, r] = [q(0, 0.5), q(1, 0.5)];
  line(ctx, l[0], l[1], r[0], r[1], "#807865");
  const [t, bt] = [q(0.5, 0), q(0.5, 1)];
  line(ctx, t[0], t[1], bt[0], bt[1], "#807865");
}

// стена «лентой»: панель с плинтусом и шапкой, окна почти сплошной лентой с жалюзи, шов панелей через 2 клетки
const WALL2: Faces = { top: "#faf9f6", left: "#f8f6f0", right: "#c1b5a7" };
const WALL2_SIDE: Faces = { top: "#faf9f6", left: "#c1b5a7", right: "#f8f6f0" };
// Полосы на наклонной грани — только целые пиксели и толщина ≥ 2: линия в 1 px при наклоне 2:1 рассыпается в «шахматку»
function windowBand(face: (u0: number, u1: number, v0: number, v1: number, c: string) => void) {
  face(0, 1, 0, 3, "#8b6a4d"); // плинтус
  face(0, 1, 3, 12, "#e9e7e0"); // нижняя панель
  face(0.1, 0.9, 16, 18, "#c1b5a7"); // подоконник
  face(0.1, 0.9, 18, 42, "#c9cdd0"); // рама
  face(0.16, 0.84, 20, 40, "#d2e2de"); // стекло
  for (const v of [22, 26, 30]) face(0.16, 0.84, v, v + 2, "#b9cfcc"); // жалюзи
  face(0.16, 0.84, 36, 40, "#e6f4f8"); // небо
}

type At = (gx: number, gy: number, h: number) => P;
// стена без поклеточной ряби по верху: одна линия по переднему краю шапки и шов по границе клетки
function wallEdges(ctx: Ctx, at: At, front: [number, number, number, number], seam: [number, number]) {
  const [ax, ay, bx, by] = front;
  const a = at(ax, ay, WALL_H), b = at(bx, by, WALL_H);
  line(ctx, a[0], a[1], b[0], b[1], OUTLINE);
  const top = at(seam[0], seam[1], WALL_H), bottom = at(seam[0], seam[1], 0);
  line(ctx, top[0], top[1], bottom[0], bottom[1], OUTLINE);
}
const atOf = (sx: number, sy: number): At => (gx, gy, h) => { const [x, y] = iso(gx, gy, h); return [sx + x, sy + y]; };

export function wallBandBack(ctx: Ctx, sx: number, sy: number, x: number) {
  box(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.72, y1: 1 }, WALL_H, WALL2, 0, false);
  windowBand((u0, u1, v0, v1, c) => onLeftFace(ctx, sx, sy, 1, u0, u1, v0, v1, c));
  wallEdges(ctx, atOf(sx, sy), [0, 1, 1, 1], [0, 1]);
  if (x === 0) { const a = atOf(sx, sy); const t = a(0, 0.72, WALL_H), u = a(0, 1, WALL_H); line(ctx, t[0], t[1], u[0], u[1], OUTLINE); }
}
export function wallBandSide(ctx: Ctx, sx: number, sy: number, y: number) {
  box(ctx, sx, sy, { x0: 0.72, x1: 1, y0: 0, y1: 1 }, WALL_H, WALL2_SIDE, 0, false);
  windowBand((u0, u1, v0, v1, c) => onRightFace(ctx, sx, sy, 1, u0, u1, v0, v1, c));
  wallEdges(ctx, atOf(sx, sy), [1, 0, 1, 1], [1, 1]);
  void y;
}

// --- палитры мебели (арт-дирекшен §3): old — прежние цвета, warm — тёплые приглушённые референса -------------------
const PALETTES = {
  old: {
    desk: { top: "#cdbb9b", left: "#a48d6b", right: "#8c7658" }, pad: "#6aa56a",
    mon: { top: "#3f4652", left: "#525b69", right: "#3a414c" }, screenOff: "#1e293b", screen1: "#7dd3fc", screen2: "#38bdf8",
    screenLine: "#e0f2fe", key: { top: "#e5e7eb", left: "#9ca3af", right: "#9ca3af" },
    chair: { top: "#5f6672", left: "#4b515b", right: "#3d424a" },
    sofa: { top: "#7c5a3c", left: "#664a31", right: "#553d28" },
    table: { top: "#cfe8f3", left: "#9cc3d4", right: "#86afc1" },
    vend: { top: "#b91c1c", left: "#dc2626", right: "#991b1b" }, vendWin: "#fde68a",
    cans: ["#2563eb", "#16a34a", "#f97316", "#a855f7"], slot: "#1f2937",
    cooler: { top: "#f1f5f9", left: "#e2e8f0", right: "#cbd5e1" }, bottle: { top: "#bae6fd", left: "#7dd3fc", right: "#38bdf8" },
    shelf: { top: "#e5e7eb", left: "#f3f4f6", right: "#d1d5db" },
    books: ["#ef4444", "#3b82f6", "#22c55e", "#eab308", "#a855f7", "#f97316", "#0ea5e9", "#f43f5e", "#84cc16", "#64748b",
      "#f59e0b"],
    pot: { top: "#7c2d12", left: "#b45309", right: "#92400e" }, leaves: ["#15803d", "#16a34a", "#22c55e", "#4ade80"],
    aqBase: { top: "#e5e7eb", left: "#9ca3af", right: "#6b7280" }, water: { top: "#bfe9f7", left: "#5eb6dd", right: "#3f97c2" },
    fish: ["#f97316", "#facc15"], weeds: "#65a30d", sand: "#65a30d",
    post: { top: "#6b7280", left: "#4b5563", right: "#374151" }, board: { top: "#fef3c7", left: "#fde68a", right: "#fcd34d" },
  },
  warm: {
    desk: { top: "#d4b296", left: "#9d806f", right: "#83624a" }, pad: "#9bb48f",
    mon: { top: "#4d403b", left: "#302f33", right: "#282529" }, screenOff: "#5c7da0", screen1: "#a4d5fd", screen2: "#b3d9f8",
    screenLine: "#ffffff", key: { top: "#e9e7e0", left: "#999b8b", right: "#999b8b" },
    chair: { top: "#999b8b", left: "#6a635f", right: "#5c5857" },
    sofa: { top: "#966642", left: "#5e4b33", right: "#4f3b2c" },
    table: { top: "#c8cfcc", left: "#a3aaa7", right: "#8c9390" },
    vend: { top: "#ee5a4a", left: "#d52726", right: "#9c1e1d" }, vendWin: "#f2e7ba",
    cans: ["#fd997f", "#bedb78", "#6a9ad8", "#f2e7ba"], slot: "#21140c",
    cooler: { top: "#f0ece8", left: "#dbd6d4", right: "#b8b2ad" }, bottle: { top: "#e6f4f8", left: "#c7e8e1", right: "#a1bcc2" },
    shelf: { top: "#f0ece8", left: "#dbd6d4", right: "#b8b2ad" },
    books: ["#d38a8a", "#8ab0d3", "#c8d38a", "#e0c28a", "#d38a8a", "#8ab0d3", "#e0c28a", "#c8d38a", "#8ab0d3", "#d38a8a",
      "#e0c28a"],
    pot: { top: "#6a3a18", left: "#c07a40", right: "#9a5a2a" }, leaves: ["#285a0c", "#438718", "#438718", "#6fc833"],
    aqBase: { top: "#3a3939", left: "#3a3939", right: "#2a2929" }, water: { top: "#c7e8e1", left: "#a1bcc2", right: "#628b88" },
    fish: ["#fd975f", "#e8c060"], weeds: "#438718", sand: "#d8c690",
    post: { top: "#63615e", left: "#63615e", right: "#43403f" }, board: { top: "#f0ece8", left: "#dbd6d4", right: "#b8b2ad" },
  },
};
const pal = () => PALETTES[ART.palette];

// падающая тень предмета на полу: сплошным цветом пола, сдвиг (+2, +1); цвет задаёт рендерер по клетке
let shadowColor = "#6a4329";
export function setShadowColor(c: string) { shadowColor = c; }
export function dropShadow(ctx: Ctx, sx: number, sy: number, r: { x0: number; x1: number; y0: number; y1: number }) {
  if (!ART.shadows) return;
  const at = (gx: number, gy: number): P => { const [x, y] = iso(gx, gy); return [sx + x + 2, sy + y + 1]; };
  fillPoly(ctx, [at(r.x0, r.y0), at(r.x1, r.y0), at(r.x1, r.y1), at(r.x0, r.y1)], shadowColor);
}
export function personShadow(ctx: Ctx, cx: number, cy: number) {
  if (!ART.shadows) return;
  ctx.fillStyle = shadowColor;
  for (const [dy, w] of [[-1, 3], [0, 5], [1, 3]] as const) ctx.fillRect(cx - w, cy + dy, w * 2, 1);
}

// --- рабочее место ----------------------------------------------------------------------------------------------------
export function desk(ctx: Ctx, sx: number, sy: number) {
  dropShadow(ctx, sx, sy, { x0: 0, x1: 1, y0: 0, y1: 1 });
  box(ctx, sx, sy, { x0: 0, x1: 1, y0: 0, y1: 1 }, 11, pal().desk);
  const pad = pal().pad;
  box(ctx, sx, sy, { x0: 0.15, x1: 0.85, y0: 0.2, y1: 0.8 }, 0, { top: pad, left: pad, right: pad }, 11, false);
}
// монитор на столе: экран смотрит на сидящего (facing — куда смотрит сидящий)
export function monitor(ctx: Ctx, sx: number, sy: number, facing: Facing, glow: boolean, ms: number) {
  if (facing === "W" || facing === "E") return monitorX(ctx, sx, sy, facing, glow, ms);
  const c = pal();
  const r = facing === "S" ? { x0: 0.2, x1: 0.8, y0: 0.62, y1: 0.74 } : { x0: 0.2, x1: 0.8, y0: 0.26, y1: 0.38 };
  box(ctx, sx, sy, r, 10, c.mon, 12);
  if (facing === "N") { // экран к зрителю; мигание не чаще 2 Гц
    const on = glow ? (Math.floor(ms / 500) % 2 ? c.screen1 : c.screen2) : c.screenOff;
    onLeftFace(ctx, sx, sy, r.y1, r.x0 + 0.06, r.x1 - 0.06, 14, 21, on);
    if (glow) onLeftFace(ctx, sx, sy, r.y1, r.x0 + 0.12, r.x0 + 0.4, 18, 19, c.screenLine);
  }
  // клавиатура — ближе к сидящему
  const k = facing === "S" ? { x0: 0.25, x1: 0.75, y0: 0.24, y1: 0.4 } : { x0: 0.25, x1: 0.75, y0: 0.6, y1: 0.76 };
  box(ctx, sx, sy, k, 1, c.key, 11, false);
}
export function chairSeat(ctx: Ctx, sx: number, sy: number) {
  dropShadow(ctx, sx, sy, { x0: 0.3, x1: 0.7, y0: 0.3, y1: 0.7 });
  box(ctx, sx, sy, { x0: 0.46, x1: 0.54, y0: 0.46, y1: 0.54 }, 5, pal().chair, 0, false);
  box(ctx, sx, sy, { x0: 0.25, x1: 0.75, y0: 0.25, y1: 0.75 }, 3, pal().chair, 5);
}
// посадка «x» (как в Game Dev Story): экран на грани +x у ближнего ряда (видно зрителю), у дальнего — спинка с решёткой
function monitorX(ctx: Ctx, sx: number, sy: number, facing: "W" | "E", glow: boolean, ms: number) {
  const c = pal();
  const r = facing === "W" ? { x0: 0.14, x1: 0.26, y0: 0.18, y1: 0.82 } : { x0: 0.74, x1: 0.86, y0: 0.18, y1: 0.82 };
  box(ctx, sx, sy, { x0: r.x0 + 0.04, x1: r.x1 - 0.04, y0: 0.42, y1: 0.58 }, 3, c.mon, 11, false);
  box(ctx, sx, sy, r, 10, c.mon, 14);
  if (facing === "W") {
    const on = glow ? (Math.floor(ms / 500) % 2 ? c.screen2 : c.screen1) : c.screenOff;
    onRightFace(ctx, sx, sy, r.x1, 0.24, 0.76, 16, 22, "#19181d");
    onRightFace(ctx, sx, sy, r.x1, 0.28, 0.72, 16.5, 21.5, on);
    if (glow) for (const [u, v] of [[0.32, 20], [0.36, 18.5]] as const) onRightFace(ctx, sx, sy, r.x1, u, u + 0.2, v, v + 0.6, "#757378");
  } else {
    for (const v of [17, 19, 21]) onRightFace(ctx, sx, sy, r.x1, 0.26, 0.74, v, v + 0.6, "#3c2e28");
  }
  box(ctx, sx, sy, { x0: 0.42, x1: 0.58, y0: 0.25, y1: 0.75 }, 1, c.key, 11, false);
}

// спинка — со стороны, противоположной столу
export function chairBack(ctx: Ctx, sx: number, sy: number, facing: Facing) {
  if (facing === "W" || facing === "E") {
    const r = facing === "W" ? { x0: 0.72, x1: 0.84, y0: 0.24, y1: 0.76 } : { x0: 0.16, x1: 0.28, y0: 0.24, y1: 0.76 };
    box(ctx, sx, sy, r, 12, pal().chair, 8);
    return;
  }
  // лицом к зрителю — высокая спинка за плечами (видно, что человек сидит в кресле); спиной — спинка закрывает поясницу
  if (facing === "S") box(ctx, sx, sy, { x0: 0.18, x1: 0.82, y0: 0.06, y1: 0.18 }, 16, pal().chair, 7);
  else box(ctx, sx, sy, { x0: 0.22, x1: 0.78, y0: 0.82, y1: 0.92 }, 9, pal().chair, 6);
}

// --- детали рабочего места (арт-дирекшен §5) ------------------------------------------------------------------------
// front — грань к зрителю (+y) видна: тумба с ящиками и ниша для ног; end — торец островка (+x): тумба, табличка
export function deskDetails(ctx: Ctx, sx: number, sy: number, front: boolean, end: boolean, plate: boolean) {
  if (ART.detail) {
    if (front) {
      onLeftFace(ctx, sx, sy, 1, 0.08, 0.46, 0, 9, "#594338"); // ниша для ног
      onLeftFace(ctx, sx, sy, 1, 0.55, 0.92, 0, 11, "#a88a78"); // тумба
      for (const v of [4, 8]) onLeftFace(ctx, sx, sy, 1, 0.55, 0.92, v, v + 1, "#594338");
      for (const v of [2, 6, 10]) onLeftFace(ctx, sx, sy, 1, 0.7, 0.78, v - 1, v, "#382a23");
    }
    if (end && !plate) {
      onRightFace(ctx, sx, sy, 1, 0.1, 0.9, 0, 11, "#8c6d58");
      for (const v of [4, 8]) onRightFace(ctx, sx, sy, 1, 0.1, 0.9, v, v + 1, "#594338");
    }
  }
  if (plate && end) { // табличка отдела на торце островка (текст — HTML-слоем)
    onRightFace(ctx, sx, sy, 1, 0.18, 0.82, 2, 10, "#b8b2ad");
    onRightFace(ctx, sx, sy, 1, 0.22, 0.78, 3, 9, "#f0ece8");
  }
}

// подставка монитора, мышь и мелочь на столе (по номеру места: кружка, бумаги, кактус или ничего)
export function monitorDetails(ctx: Ctx, sx: number, sy: number, facing: Facing, glow: boolean, seed: number) {
  if (!ART.detail || facing === "W" || facing === "E") return;
  const near = facing === "S" ? 0.62 : 0.26; // монитор
  box(ctx, sx, sy, { x0: 0.46, x1: 0.54, y0: near + 0.02, y1: near + 0.1 }, 1, pal().mon, 11, false);
  const ky = facing === "S" ? 0.32 : 0.68; // клавиатура и мышь — у сидящего
  box(ctx, sx, sy, { x0: 0.8, x1: 0.88, y0: ky - 0.04, y1: ky + 0.04 }, 1, { top: "#d6c5b7", left: "#b8a99c", right: "#a39588" }, 11, false);
  if (facing === "N" && glow) for (const [u, v] of [[0.3, 16], [0.36, 15]] as const)
    onLeftFace(ctx, sx, sy, near + 0.12, u, u + 0.24, v, v + 1, "#757378");
  const item = seed % 4;
  const iy = facing === "S" ? 0.12 : 0.84;
  if (item === 1) box(ctx, sx, sy, { x0: 0.08, x1: 0.16, y0: iy - 0.04, y1: iy + 0.04 }, 3, { top: "#f8f6f0", left: "#d52726", right: "#9c1e1d" }, 11, false);
  if (item === 2) box(ctx, sx, sy, { x0: 0.06, x1: 0.24, y0: iy - 0.06, y1: iy + 0.06 }, 1, { top: "#ffffff", left: "#e9e7e0", right: "#e9e7e0" }, 11, false);
  if (item === 3) {
    box(ctx, sx, sy, { x0: 0.08, x1: 0.16, y0: iy - 0.04, y1: iy + 0.04 }, 2, { top: "#9a5a2a", left: "#c07a40", right: "#9a5a2a" }, 11, false);
    box(ctx, sx, sy, { x0: 0.1, x1: 0.14, y0: iy - 0.02, y1: iy + 0.02 }, 3, { top: "#6fc833", left: "#438718", right: "#285a0c" }, 13, false);
  }
}

// кресло на крестовине с колёсиками и подлокотниками
export function chairDetails(ctx: Ctx, sx: number, sy: number) {
  if (!ART.detail) return;
  const cx = sx, cy = sy + TH / 2;
  for (const [dx, dy] of [[-5, 1], [5, 1], [-3, 3], [3, 3], [0, -2]] as const) {
    line(ctx, cx, cy, cx + dx, cy + dy, "#33241e");
    ctx.fillStyle = "#1d0d0b";
    ctx.fillRect(cx + dx, cy + dy, 1, 1);
  }
  for (const x0 of [0.2, 0.72]) box(ctx, sx, sy, { x0, x1: x0 + 0.08, y0: 0.3, y1: 0.7 }, 1, pal().chair, 9, false);
}

// --- зона отдыха ------------------------------------------------------------------------------------------------------
export function furniture(ctx: Ctx, kind: FurnitureKind, sx: number, sy: number, facing: Facing | undefined, ms: number) {
  const c = pal();
  switch (kind) {
    case "sofa": {
      dropShadow(ctx, sx, sy, { x0: 0.05, x1: 0.95, y0: 0.15, y1: 0.85 });
      box(ctx, sx, sy, { x0: 0.05, x1: 0.95, y0: 0.15, y1: 0.85 }, 7, c.sofa);
      const back = facing === "N" ? { x0: 0.05, x1: 0.95, y0: 0.72, y1: 0.88 } : { x0: 0.05, x1: 0.95, y0: 0.1, y1: 0.26 };
      box(ctx, sx, sy, back, 9, c.sofa, 7);
      return;
    }
    case "table": {
      dropShadow(ctx, sx, sy, { x0: 0.1, x1: 0.9, y0: 0.1, y1: 0.9 });
      box(ctx, sx, sy, { x0: 0.1, x1: 0.9, y0: 0.1, y1: 0.9 }, 7, c.table);
      const glint = { top: "#e8eeec", left: "#e8eeec", right: "#e8eeec" };
      if (ART.palette === "warm") box(ctx, sx, sy, { x0: 0.3, x1: 0.4, y0: 0.2, y1: 0.8 }, 0, glint, 7, false);
      return;
    }
    case "vending":
      dropShadow(ctx, sx, sy, { x0: 0.1, x1: 0.9, y0: 0.2, y1: 0.9 });
      box(ctx, sx, sy, { x0: 0.1, x1: 0.9, y0: 0.2, y1: 0.9 }, 36, c.vend);
      onLeftFace(ctx, sx, sy, 0.9, 0.18, 0.62, 12, 32, c.vendWin);
      for (let i = 0; i < 4; i++) onLeftFace(ctx, sx, sy, 0.9, 0.2, 0.6, 14 + i * 5, 16 + i * 5, c.cans[i]);
      onLeftFace(ctx, sx, sy, 0.9, 0.68, 0.84, 18, 24, c.slot);
      return;
    case "cooler":
      dropShadow(ctx, sx, sy, { x0: 0.28, x1: 0.72, y0: 0.3, y1: 0.74 });
      box(ctx, sx, sy, { x0: 0.28, x1: 0.72, y0: 0.3, y1: 0.74 }, 18, c.cooler);
      box(ctx, sx, sy, { x0: 0.34, x1: 0.66, y0: 0.36, y1: 0.68 }, 9, c.bottle, 18);
      if (ART.palette === "warm") {
        onLeftFace(ctx, sx, sy, 0.74, 0.4, 0.46, 10, 11, "#d52726");
        onLeftFace(ctx, sx, sy, 0.74, 0.54, 0.6, 10, 11, "#3e4a78");
      }
      return;
    case "shelf":
      dropShadow(ctx, sx, sy, { x0: 0.05, x1: 0.95, y0: 0.5, y1: 0.9 });
      box(ctx, sx, sy, { x0: 0.05, x1: 0.95, y0: 0.5, y1: 0.9 }, 24, c.shelf);
      for (let i = 0; i < 6; i++) onLeftFace(ctx, sx, sy, 0.9, 0.1 + i * 0.13, 0.19 + i * 0.13, 4, 11, c.books[i]);
      for (let i = 0; i < 5; i++) onLeftFace(ctx, sx, sy, 0.9, 0.12 + i * 0.16, 0.22 + i * 0.16, 14, 21, c.books[6 + i]);
      return;
    case "plant":
      dropShadow(ctx, sx, sy, { x0: 0.3, x1: 0.7, y0: 0.3, y1: 0.7 });
      box(ctx, sx, sy, { x0: 0.3, x1: 0.7, y0: 0.3, y1: 0.7 }, 7, c.pot);
      for (const [dx, dy, r, i] of [[0, -14, 6, 0], [-4, -11, 5, 1], [4, -10, 5, 2], [0, -19, 4, 3]] as const)
        blob(ctx, sx + dx, sy + TH / 2 + dy, r, c.leaves[i]);
      return;
    case "aquarium": {
      dropShadow(ctx, sx, sy, { x0: 0.08, x1: 0.92, y0: 0.3, y1: 0.8 });
      box(ctx, sx, sy, { x0: 0.08, x1: 0.92, y0: 0.3, y1: 0.8 }, 8, c.aqBase);
      box(ctx, sx, sy, { x0: 0.08, x1: 0.92, y0: 0.3, y1: 0.8 }, 15, c.water, 8);
      const fx = (Math.floor(ms / 400) % 6) / 10;
      onLeftFace(ctx, sx, sy, 0.8, 0.2 + fx, 0.28 + fx, 13, 15, c.fish[0]);
      onLeftFace(ctx, sx, sy, 0.8, 0.6 - fx / 2, 0.66 - fx / 2, 18, 19, c.fish[1]);
      onLeftFace(ctx, sx, sy, 0.8, 0.12, 0.88, 8, 10, c.sand);
      onLeftFace(ctx, sx, sy, 0.8, 0.14, 0.2, 10, 15, c.weeds);
      return;
    }
    case "whiteboard":
      whiteboard(ctx, sx, sy);
      return;
    case "reception": { // стойка: белый верх с выступом, на ней монитор спинкой к зрителю
      const R = { top: "#f0ece8", left: "#d6c5b7", right: "#b09883" };
      dropShadow(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.2, y1: 0.8 });
      box(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.22, y1: 0.78 }, 12, R);
      box(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.16, y1: 0.84 }, 2, R, 12);
      box(ctx, sx, sy, { x0: 0.3, x1: 0.7, y0: 0.3, y1: 0.4 }, 8, c.mon, 14);
      return;
    }
    case "cabinet": { // низкий белый шкаф с папками сверху и двумя дверцами
      dropShadow(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.4, y1: 0.9 });
      box(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.45, y1: 0.9 }, 14, c.shelf);
      onLeftFace(ctx, sx, sy, 0.9, 0.49, 0.51, 1, 12, "#b8b2ad");
      for (let i = 0; i < 5; i++) box(ctx, sx, sy, { x0: 0.08 + i * 0.17, x1: 0.18 + i * 0.17, y0: 0.5, y1: 0.8 }, 6,
        { top: c.books[i], left: c.books[i], right: "#8a8580" }, 14, false);
      return;
    }
    case "leaddesk": // стол руководителя: стол + монитор спинкой к залу
      desk(ctx, sx, sy);
      box(ctx, sx, sy, { x0: 0.25, x1: 0.75, y0: 0.2, y1: 0.32 }, 10, c.mon, 12);
      return;
    case "leadchair":
      chairSeat(ctx, sx, sy);
      chairBack(ctx, sx, sy, "S");
      return;
    case "partition": // низкая перегородка лобби
      dropShadow(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.4, y1: 0.6 });
      box(ctx, sx, sy, { x0: 0, x1: 1, y0: 0.4, y1: 0.6 }, 16, { top: "#faf9f6", left: "#e9e7e0", right: "#c1b5a7" });
      onLeftFace(ctx, sx, sy, 0.6, 0, 1, 0, 3, "#8b6a4d");
  }
}

function blob(ctx: Ctx, cx: number, cy: number, r: number, color: string) {
  ctx.fillStyle = color;
  for (let y = -r; y <= r; y++) {
    const w = Math.round(Math.sqrt(r * r - y * y));
    ctx.fillRect(Math.round(cx - w), Math.round(cy + y), w * 2, 1);
  }
  ctx.fillStyle = OUTLINE;
}

// табличка отдела: стойка с доской (текст — HTML-слоем)
export function plaque(ctx: Ctx, sx: number, sy: number) {
  dropShadow(ctx, sx, sy, { x0: 0.4, x1: 0.6, y0: 0.4, y1: 0.6 });
  box(ctx, sx, sy, { x0: 0.45, x1: 0.55, y0: 0.45, y1: 0.55 }, 12, pal().post);
  box(ctx, sx, sy, { x0: 0.1, x1: 0.9, y0: 0.42, y1: 0.58 }, 10, pal().board, 12);
}

// --- персонажи --------------------------------------------------------------------------------------------------------
export type CharFrame = "sit" | "type1" | "type2" | "read1" | "read2" | "walk1" | "walk2" | "stand";
export type View = "front" | "back";
export const CHAR_W = 16, CHAR_H = 24;

const FRONT = [
  "................",
  ".....oooooo.....",
  "....ohhhhhho....",
  "....ohhhhhho....",
  "....ohssssho....",
  "....osesseso....",
  "....osssssso....",
  ".....oossoo.....",
  "......osso......",
  "...otttttttto...",
  "..otttttttttto..",
  "..otttttttttto..",
  "..osttttttttso..",
  "..osttttttttso..",
  "...otttttttto...",
  "...oppppppppo...",
  "...oppppppppo...",
  "...opppoopppo...",
  "...oppo..oppo...",
  "...oppo..oppo...",
  "...okko..okko...",
  "...oooo..oooo...",
  "................",
  "................",
];

type Grid = string[][];
const clone = (rows: string[]): Grid => rows.map((r) => r.split(""));
const put = (g: Grid, y: number, x: number, c: string) => { if (g[y] && x >= 0 && x < 16) g[y][x] = c; };
const row = (g: Grid, y: number, s: string) => { g[y] = s.split(""); };

function hairStyle(g: Grid, style: number, view: View) {
  if (view === "back") for (let y = 4; y <= 7; y++) for (let x = 5; x <= 10; x++) if (y < 7 || (x > 5 && x < 10)) put(g, y, x, "h");
  if (style === 1 || style === 2) { // каре / длинные: пряди по бокам
    const bottom = style === 2 ? 12 : 7;
    for (let y = 3; y <= bottom; y++) { put(g, y, 4, "h"); put(g, y, 11, "h"); put(g, y, 3, "o"); put(g, y, 12, "o"); }
  }
  if (style === 3) { row(g, 0, "......oooo......"); put(g, 1, 6, "h"); put(g, 1, 7, "h"); put(g, 1, 8, "h"); put(g, 1, 9, "h"); }
  if (style === 4) { put(g, 3, 5, view === "front" ? "s" : "h"); put(g, 3, 10, view === "front" ? "s" : "h"); } // коротко
  if (style === 5 && view === "front") { put(g, 4, 5, "h"); put(g, 4, 6, "h"); put(g, 4, 7, "h"); } // чёлка набок
  if (style === 0) { put(g, 0, 6, "o"); put(g, 0, 9, "o"); put(g, 1, 6, "h"); put(g, 1, 9, "h"); } // вихры
}

function outfit(g: Grid, look: Look, view: View) {
  if (view === "back") {
    if (look.outfit === "hoodie") for (let x = 5; x <= 10; x++) put(g, 9, x, "a");
    return;
  }
  if (look.outfit === "shirt") { put(g, 9, 7, "w"); put(g, 9, 8, "w"); }
  if (look.outfit === "jacket") {
    for (let y = 9; y <= 14; y++) { put(g, y, 7, "a"); put(g, y, 8, "a"); }
    put(g, 10, 7, "r"); put(g, 11, 8, "r"); put(g, 12, 7, "r");
  }
  if (look.outfit === "hoodie") { for (let x = 5; x <= 10; x++) put(g, 9, x, "a"); put(g, 13, 6, "a"); put(g, 13, 9, "a"); }
}

function accessory(g: Grid, look: Look, view: View) {
  if (look.accessory === "glasses" && view === "front") {
    put(g, 5, 5, "g"); put(g, 5, 7, "g"); put(g, 5, 8, "g"); put(g, 5, 10, "g");
  }
  if (look.accessory === "headset") {
    for (let x = 5; x <= 10; x++) put(g, 1, x, "m");
    for (let y = 4; y <= 6; y++) { put(g, y, 4, "m"); put(g, y, 11, "m"); }
    if (view === "front") { put(g, 7, 10, "m"); put(g, 7, 9, "m"); }
  }
}

function pose(g: Grid, frame: CharFrame, view: View) {
  const sitting = frame !== "walk1" && frame !== "walk2" && frame !== "stand";
  if (sitting) { row(g, 16, "...oppppppppo..."); for (let y = 17; y < 24; y++) row(g, y, "................"); }
  if (frame === "type1") { put(g, 12, 3, "t"); put(g, 11, 3, "s"); put(g, 13, 12, "s"); }
  if (frame === "type2") { put(g, 13, 3, "s"); put(g, 12, 12, "t"); put(g, 11, 12, "s"); }
  if ((frame === "read1" || frame === "read2") && view === "front") {
    const dy = frame === "read2" ? 1 : 0;
    for (let y = 11 + dy; y <= 13 + dy; y++) for (let x = 5; x <= 10; x++) put(g, y, x, "w");
  }
  if (frame === "walk1") { row(g, 18, "..oppo....oppo.."); row(g, 19, "..oppo....oppo.."); row(g, 20, "..okko....okko.."); row(g, 21, "..oooo....oooo.."); }
  if (frame === "walk2") { row(g, 18, "....oppooppo...."); row(g, 19, "....oppooppo...."); row(g, 20, "....okkookko...."); row(g, 21, "....oooooooo...."); }
}

export function characterGrid(look: Look, frame: CharFrame, view: View): Grid {
  const g = clone(FRONT);
  hairStyle(g, look.hairStyle, view);
  outfit(g, look, view);
  accessory(g, look, view);
  pose(g, frame, view);
  return g;
}

function darker(color: string): string {
  const m = /hsl\((\d+) (\d+)% (\d+)%\)/.exec(color);
  return m ? `hsl(${m[1]} ${m[2]}% ${Math.max(10, Number(m[3]) - 18)}%)` : color;
}

export function colorsOf(look: Look): Record<string, string> {
  const jacket = look.outfit === "jacket";
  return { o: OUTLINE, h: look.hair, s: look.skin, e: "#1f2937", t: jacket ? darker(look.pants) : look.shirt,
    a: jacket ? look.shirt : darker(look.shirt), w: "#f8fafc", r: "#b91c1c", p: look.pants, k: "#1f2937",
    g: "#111827", m: "#4b5563" };
}

export function drawCharacter(ctx: Ctx, look: Look, frame: CharFrame, view: View, x: number, y: number, mirror = false) {
  const g = characterGrid(look, frame, view);
  const colors = colorsOf(look);
  for (let r = 0; r < CHAR_H; r++) {
    for (let c = 0; c < CHAR_W; c++) {
      const color = colors[g[r][c]];
      if (!color) continue;
      ctx.fillStyle = color;
      ctx.fillRect(x + (mirror ? CHAR_W - 1 - c : c), y + r, 1, 1);
    }
  }
}

export function drawCharacterCached(ctx: Ctx, key: string, look: Look, frame: CharFrame, view: View, x: number, y: number,
  mirror = false) {
  const img = sprite(`c|${key}|${frame}|${view}|${mirror ? 1 : 0}`, CHAR_W, CHAR_H,
    (g) => drawCharacter(g, look, frame, view, 0, 0, mirror));
  ctx.drawImage(img, x, y);
}

// --- кэш спрайтов: каждый вид рисуется один раз в скрытый canvas -------------------------------------------------------
const cache = new Map<string, HTMLCanvasElement>();
export function sprite(id: string, w: number, h: number, draw: (ctx: Ctx) => void): HTMLCanvasElement {
  let c = cache.get(id);
  if (!c) {
    c = document.createElement("canvas");
    c.width = w; c.height = h;
    const ctx = c.getContext("2d");
    if (ctx) draw(ctx);
    cache.set(id, c);
    if (cache.size > 2000) cache.delete(cache.keys().next().value as string);
  }
  return c;
}

// Контур только по силуэту: прозрачный пиксель рядом с непрозрачным становится тёмным (слой предметов поверх пола)
export function silhouette(ctx: Ctx, w: number, h: number) {
  const img = ctx.getImageData(0, 0, w, h);
  const d = img.data;
  const solid = (i: number) => d[i * 4 + 3] > 0;
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = y * w + x;
    if (solid(i)) continue;
    if ((x > 0 && solid(i - 1)) || (x < w - 1 && solid(i + 1)) || (y > 0 && solid(i - w)) || (y < h - 1 && solid(i + w))) out[i] = 1;
  }
  for (let i = 0; i < out.length; i++) if (out[i]) { d[i * 4] = 0x21; d[i * 4 + 1] = 0x14; d[i * 4 + 2] = 0x0c; d[i * 4 + 3] = 255; }
  ctx.putImageData(img, 0, 0);
}

export const SLAB_H = 18; // 6 px плиты пола + 12 px кирпича
// срез плиты под передними кромками пола: side "y" — грань к зрителю слева, "x" — справа
export function slab(ctx: Ctx, sx: number, sy: number, side: "x" | "y") {
  const a: P = side === "y" ? [sx - TW / 2, sy + TH / 2] : [sx, sy + TH];
  const b: P = side === "y" ? [sx, sy + TH] : [sx + TW / 2, sy + TH / 2];
  const band = (z0: number, z1: number, c: string) =>
    fillPoly(ctx, [[a[0], a[1] + z0], [b[0], b[1] + z0], [b[0], b[1] + z1], [a[0], a[1] + z1]], c);
  band(0, 6, side === "y" ? "#6b4a33" : "#553423");
  band(6, SLAB_H, side === "y" ? "#724126" : "#5e3520");
  for (const z of [10, 14]) line(ctx, a[0], a[1] + z, b[0], b[1] + z, "#553423"); // швы кладки
  const k = side === "y" ? 0.5 : 0.25;
  line(ctx, a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k + 6, a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k + 10, "#553423");
}

// --- чиби (арт-дирекшен §4) ----------------------------------------------------------------------------------------
export function drawChibi(ctx: Ctx, key: string, pose: ChibiPose, view: ChibiView, x: number, y: number, mirror = false) {
  const img = sprite(`chibi|${key}|${pose}|${view}|${mirror ? 1 : 0}`, CHAR_W, CHAR_H, (g) => {
    const look = chibiLook(key);
    const grid = chibiGrid(look, pose, view);
    for (let r = 0; r < CHAR_H; r++) for (let c = 0; c < CHAR_W; c++) {
      const color = chibiColor(grid[r][c], r, look);
      if (!color) continue;
      g.fillStyle = color;
      g.fillRect(mirror ? CHAR_W - 1 - c : c, r, 1, 1);
    }
  });
  ctx.drawImage(img, x, y);
}
