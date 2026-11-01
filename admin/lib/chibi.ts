// Чиби-персонажи офиса (арт-дирекшен 2026-10-21 §4): матрицы 16×24, причёски, одежда, аксессуары, рампы цветов.
// Матрицы смотрят влево; вправо — зеркально. Только данные и сборка сетки — рисует iso-sprites.
import { hash } from "./office";

export type ChibiView = "front" | "back";
export type ChibiPose = "stand" | "walk1" | "walk2" | "sit" | "type1" | "type2";

// легенда: . пусто, o контур, H/h/d волосы (блик/основа/тень), S/s/k кожа, e глаз, c румянец, m рот,
// A акцент, T/t/u одежда (светлый/основа/тень), P/p брюки, F обувь, W белая рубашка, R галстук, g оправа, l линза,
// M гарнитура
const FRONT = [
  "....oooooooo....",
  "...ohhHHHhhho...",
  "..ohhHHhhhhhdo..",
  "..ohhhhhhhhhddo.",
  "..ohhhsshhhhddo.",
  "..ohsssssshhkdo.",
  "..osesssesshkdo.",
  "..osesssessskdo.",
  "..ocsssssscsko..",
  "...ossmmssko....",
  "....oooskooo....",
  "...ottAAtttto...",
  "..otTttAtttttuo.",
  "..otTttAttttuuo.",
  "..otTttttttttuo.",
  "..otTttttttttuo.",
  "..ostttttttttso.",
  "..okouuuuuuuoko.",
  "...oPPPPPPPPo...",
  "...oPPpooPPpo...",
  "...oPPpo.oPpo...",
  "...oPPpo.oPpo...",
  "..oFFFo..oFFo...",
  "..ooooo..oooo...",
];
const BACK_HEAD = [
  "....oooooooo....",
  "...ohhHHHhhho...",
  "..ohHHHhhhhhho..",
  "..ohHhhhhhhhhdo.",
  "..ohhhhhhhhhhdo.",
  "..okhhhhhhhhhdo.",
  "..oskhhhhhhhddo.",
  "..oskhhhhhhhddo.",
  "...okhhhhhhddo..",
  "...oohhhhhddoo..",
  ".....okkkko.....",
];
const SIT_BACK = [ // ближний ряд, спиной 3/4; ниже — спинка кресла
  "...otttttttto...",
  "..otTtttttttuo..",
  ".osTTttttttuuo..",
  ".ooTTtttttuuuo..",
  "..ottttttttuuo..",
  "...ouuuuuuuuo...",
];
const SIT_FRONT = [ // дальний ряд, лицом 3/4; кисти на столе
  "...ottAAtttto...",
  "..otTttAtttttuo.",
  "..otTttAttttuuo.",
  "..soTttttttuos..",
  "..ssouuuuuuuoss.",
];
// ноги сидящего: колени к зрителю (лицом) / под сиденьем (спиной) — видны при посадке «y» и на диване
const SIT_LEGS_FRONT = [
  "...oPPPPPPPPo...",
  "...oPPpooPPpo...",
  "...oPpo..oPpo...",
  "..oFFFo..oFFFo..",
  "..ooooo..ooooo..",
];
const SIT_LEGS_BACK = [
  "...oPPPPPPPPo...",
  "...oPPpooPPpo...",
  "...oFFo..oFFo...",
  "...oooo..oooo...",
];
const EMPTY = "................";

export const ROWS = { FRONT, BACK_HEAD, SIT_BACK, SIT_FRONT, SIT_LEGS_FRONT, SIT_LEGS_BACK };

export type Grid = string[][];
const put = (g: Grid, y: number, x: number, c: string) => { if (g[y] && x >= 0 && x < 16) g[y][x] = c; };
const setRow = (g: Grid, y: number, s: string) => { g[y] = s.split(""); };

export const HAIR_STYLES = 6;
export const OUTFITS = ["shirt", "jacket", "hoodie", "tshirt", "vest"] as const;
export type Outfit = (typeof OUTFITS)[number];
export type ChibiLook = { hairStyle: number; outfit: Outfit; accessory: "none" | "glasses" | "headset"; skin: number;
  hair: number; cloth: number; accent: number };

export function chibiLook(key: string): ChibiLook {
  const h = hash(key);
  return { hairStyle: h % HAIR_STYLES, outfit: OUTFITS[(h >>> 4) % OUTFITS.length],
    accessory: (["none", "glasses", "headset"] as const)[(h >>> 9) % 3], skin: (h >>> 12) % 4, hair: (h >>> 15) % 6,
    cloth: (h >>> 18) % 8, accent: (h >>> 21) % 8 };
}

function hair(g: Grid, style: number, view: ChibiView) {
  if (style === 1 || style === 2) { // каре / длинные: пряди по бокам
    if (view === "front") setRow(g, 4, "..ohhhhhhhhhddo.");
    const bottom = style === 2 ? 15 : 9;
    for (let y = 5; y <= Math.min(bottom, 9); y++) { put(g, y, 2, "h"); put(g, y, 3, "h"); put(g, y, 12, "d"); put(g, y, 13, "d");
      put(g, y, 1, "o"); put(g, y, 14, "o"); }
    if (view === "front") put(g, 8, 3, "h");
    if (style === 2) for (let y = 10; y <= 15; y++) { const w = y < 13 ? 2 : 1; for (let i = 0; i < w; i++) put(g, y, 12 + i, i ? "d" : "h"); put(g, y, 12 + w, "o"); }
  }
  if (style === 3) { setRow(g, 0, "...o.oo.oo.o...."); setRow(g, 1, "..ohohhohhoho..."); put(g, 1, 4, "H"); put(g, 1, 7, "H"); }
  if (style === 4) { // пучок
    for (let y = 0; y <= 2; y++) for (let x = 10; x <= 13; x++) put(g, y, x, (x === 10 || x === 13 || y === 0) ? "o" : y === 1 ? "h" : "d");
    if (view === "front") for (let x = 5; x <= 9; x++) put(g, 4, x, "s");
  }
  if (style === 5 && view === "front") { // чёлка набок закрывает дальний глаз
    for (let x = 3; x <= 6; x++) { put(g, 4, x, x === 5 ? "H" : "h"); put(g, 5, x, "h"); }
    for (let x = 3; x <= 5; x++) put(g, 6, x, "h");
  }
}

function outfit(g: Grid, o: Outfit, view: ChibiView, rows: [number, number]) {
  const [a, b] = rows; // строки корпуса в этой позе
  const inBody = (y: number) => y >= a && y <= b;
  if (view === "back") return;
  if (o === "jacket") { for (let y = a; y <= b; y++) { put(g, y, 6, "W"); put(g, y, 7, inBody(y) && y > a ? "R" : "W"); put(g, y, 8, "W"); } }
  if (o === "hoodie") { for (let x = 4; x <= 10; x++) put(g, a, x, "T"); put(g, a + 1, 6, "A"); put(g, a + 1, 8, "A"); put(g, a + 2, 6, "A"); put(g, a + 2, 8, "A");
    if (b - a >= 4) for (let x = 5; x <= 10; x++) put(g, a + 4, x, "u"); }
  if (o === "tshirt") { for (let x = 6; x <= 8; x++) put(g, a, x, "k"); for (let y = a + 3; y <= b; y++) { if (g[y][2] === "t" || g[y][2] === "T") put(g, y, 2, "s"); } }
  if (o === "vest") { for (let y = a + 1; y <= b; y++) for (let x = 4; x <= 11; x++) if ("tTu".includes(g[y][x])) put(g, y, x, x === 4 || x === 11 ? "W" : g[y][x]); }
}

function accessory(g: Grid, acc: ChibiLook["accessory"], view: ChibiView) {
  if (acc === "glasses" && view === "front") {
    for (const x of [3, 4, 5, 7, 8, 9]) put(g, 6, x, "g");
    put(g, 6, 4, "l"); put(g, 6, 8, "l"); put(g, 6, 6, "g");
  }
  if (acc === "headset") {
    for (let x = 4; x <= 11; x++) if (g[1][x] !== ".") put(g, 1, x, "M");
    for (let y = 5; y <= 7; y++) { put(g, y, 11, "M"); put(g, y, 12, "M"); }
    if (view === "front") { put(g, 9, 8, "M"); put(g, 9, 9, "M"); }
  }
}

export function chibiGrid(look: ChibiLook, pose: ChibiPose, view: ChibiView): Grid {
  const head = (view === "front" ? FRONT.slice(0, 11) : BACK_HEAD).map((r) => r.split(""));
  const sitting = pose === "sit" || pose === "type1" || pose === "type2";
  let body: string[];
  if (sitting) body = view === "front" ? [...SIT_FRONT, ...SIT_LEGS_FRONT] : [...SIT_BACK, ...SIT_LEGS_BACK];
  else body = FRONT.slice(11).map((r) => (view === "back" ? r.replace(/A/g, "t").replace(/T/g, "t") : r));
  const g: Grid = [...head, ...body.map((r) => r.split(""))];
  while (g.length < 24) g.push(EMPTY.split(""));
  if (pose === "type1" || pose === "type2") {
    if (view === "back") { if (pose === "type2") { put(g, 13, 1, "o"); put(g, 14, 1, "s"); } }
    else if (pose === "type2") { const r14 = g[14], r15 = g[15]; g[14] = r15; g[15] = r14; }
  }
  if (pose === "walk1" || pose === "walk2") { // ноги вперёд-назад, голова на walk2 ниже на 1
    const legs = pose === "walk1"
      ? ["...oPPPPPPPPo...", "...oPPpooPPpo...", "..oPPpo..oPpo...", "..oPPpo..oPpo...", ".oFFFo...oFFo...", ".ooooo...oooo..."]
      : ["...oPPPPPPPPo...", "...oPPpooPPpo...", "...oPpo.oPPpo...", "...oPpo.oPPpo...", "...oFFo.oFFFo...", "...oooo.ooooo..."];
    legs.forEach((r, i) => setRow(g, 18 + i, r));
    if (pose === "walk2") { g.unshift(EMPTY.split("")); g.splice(18, 1); }
  }
  hair(g, look.hairStyle, view);
  outfit(g, look.outfit, view, sitting ? [11, view === "front" ? 15 : 16] : [11, 17]);
  accessory(g, look.accessory, view);
  return g;
}

// --- рампы цветов (арт-дирекшен §3) ----------------------------------------------------------------------------
export const SKIN = [
  ["#fde5cc", "#f3c9a4", "#d79f7c", "#97503f"], ["#ecc49a", "#d4a476", "#b47c55", "#7a4430"],
  ["#d4a072", "#b37a4d", "#8f5a36", "#5a321e"], ["#a8714a", "#87542f", "#683d20", "#3e2111"],
];
export const HAIR = [
  ["#5a5a6a", "#2f2b32", "#1d1a20", "#100c0e"], ["#a06a45", "#6e472b", "#4f311d", "#2e1b10"],
  ["#ed8931", "#e46b2a", "#c14733", "#580c25"], ["#f6e2a0", "#e0bf6e", "#b8924a", "#6b5222"],
  ["#e4e4e4", "#b4b4b4", "#868686", "#4a4a4a"], ["#b0503e", "#86372c", "#5e241d", "#33100c"],
];
export const CLOTH = [
  ["#ffffff", "#e9e7e0", "#b9b4aa"], ["#8a8a8e", "#63615e", "#43403f"], ["#5a6aa0", "#3e4a78", "#283055"],
  ["#d6ec9a", "#c1dc75", "#8fa652"], ["#ffb088", "#fd975f", "#d0703e"], ["#f0a8cc", "#cd7faf", "#9a5682"],
  ["#8fd0c8", "#5aa8a0", "#3a7a74"], ["#e8c060", "#c89a3a", "#95702a"],
];
export const INK = "#21140c";

// цвет пикселя: контур в волосах — тёмный тон волос, у лица — контур кожи, ниже — общий контур
export function chibiColor(c: string, row: number, look: ChibiLook): string | null {
  const s = SKIN[look.skin], h = HAIR[look.hair];
  const cloth = look.outfit === "jacket" ? CLOTH[1] : CLOTH[look.cloth];
  const acc = CLOTH[look.accent];
  switch (c) {
    case ".": return null;
    case "o": return row <= 4 ? h[3] : row <= 10 ? s[3] : INK;
    case "H": return h[0]; case "h": return h[1]; case "d": return h[2];
    case "S": return s[0]; case "s": return s[1]; case "k": return s[2];
    case "e": return INK; case "c": return "#e8a090"; case "m": return "#9f2732";
    case "A": return acc[1]; case "T": return cloth[0]; case "t": return cloth[1]; case "u": return cloth[2];
    case "P": return "#3e4a5e"; case "p": return "#2a3242"; case "F": return "#382a23";
    case "W": return "#e9e7e0"; case "R": return acc[2]; case "g": return INK; case "l": return "#d2e2de";
    case "M": return "#43403f";
    default: return null;
  }
}
