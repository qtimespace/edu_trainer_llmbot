// Портрет агента в духе Stardew (арт-дирекшен 2026-10-21 §7): растр 88×120 — рама, фон, бюст 3/4 по внешности чиби.
// Чистая функция без canvas: проверяется тестами, рисует components/office/portrait.ts. Бюст — слои lib/portrait-art.
// Легенда слоёв: кожа 1–5 (блик…контур), глаза w i I p * l, лицо m n c, одежда A B C D W R, волосы H h d e o,
// аксессуары g G (очки), M N (гарнитура); «.» — прозрачно.
import { CLOTH, chibiLook, HAIR, OUTFITS, SKIN } from "./chibi";
import { BASE, BUST_H, BUST_W, GLASSES, HAIR_BACK, HAIR_FRONT, HEADSET, OUTFIT } from "./portrait-art";
import { hash } from "./office";

export const PW = 88, PH = 120;
export type FrameStyle = "boards" | "simple";
export type Raster = { px: (string | null)[]; plate: { x: number; y: number; w: number; h: number }; outline: number };

const EYES = [["#a07040", "#5a3418"], ["#6fa858", "#2f5a24"], ["#6a9ad8", "#2a4a7a"], ["#a77497", "#5a3a6a"]];

export function portraitRaster(key: string, frame: FrameStyle): Raster {
  const px: (string | null)[] = new Array(PW * PH).fill(null);
  const set = (x: number, y: number, c: string) => { if (x >= 0 && y >= 0 && x < PW && y < PH) px[y * PW + x] = c; };
  const rect = (x: number, y: number, w: number, h: number, c: string) => {
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) set(x + i, y + j, c);
  };
  const seed = hash(key);

  // --- фон и рама -------------------------------------------------------------------------------------------------
  rect(0, 0, PW, PH, "#041742");
  for (let i = 0; i < 10; i++) set((seed >>> i) % PW, ((seed >>> (i + 3)) * 7 + i * 29) % PH, i % 2 ? "#3a6ad0" : "#7aa0f0");
  for (const [sx, sy] of [[8 + (seed % 9), 4], [80 - (seed % 7), 112]]) { // искры-плюсы
    set(sx, sy, "#ffffff");
    for (const d of [1, 2]) { set(sx - d, sy, "#cfe0ff"); set(sx + d, sy, "#cfe0ff"); set(sx, sy - d, "#cfe0ff"); set(sx, sy + d, "#cfe0ff"); }
  }
  const wood = frame === "boards" ? { base: "#cc683d", hi: "#e08a52", lo: "#8a4d2a", grain: "#5b2e13", ink: "#241f27" }
    : { base: "#b5652e", hi: "#d4864a", lo: "#7a3e1a", grain: "#7a3e1a", ink: "#7a3e1a" };
  const board = (x: number, y: number, w: number, h: number, vertical: boolean) => {
    rect(x - 1, y - 1, w + 2, h + 2, wood.ink);
    rect(x, y, w, h, wood.base);
    if (vertical) { rect(x, y, 1, h, wood.hi); rect(x + w - 2, y, 2, h, wood.lo); }
    else { rect(x, y, w, 1, wood.hi); rect(x, y + h - 2, w, 2, wood.lo); }
    if (frame === "boards") for (let k = 0; k < 6; k++) { // волокна
      const t = ((seed >>> (k * 2)) % (vertical ? h - 8 : w - 8)) + 3;
      if (vertical) rect(x + 2 + (k % 3), y + t, 1, 3 + (k % 4), wood.grain);
      else rect(x + t, y + 2 + (k % 3), 3 + (k % 4), 1, wood.grain);
    }
  };
  if (frame === "boards") {
    board(4, 2, 8, 116, true); board(76, 2, 8, 116, true); // вертикальные — под горизонтальными
    board(0, 8, 88, 8, false); board(0, 102, 88, 8, false);
  } else {
    rect(3, 7, 82, 106, wood.lo); rect(4, 8, 80, 104, wood.base);
  }
  rect(12, 16, 64, 86, "#d6ab76"); // панель
  rect(12, 16, 64, 2, "#c3945d"); rect(12, 16, 2, 86, "#c3945d");
  for (const [cx, cy] of [[12, 16], [74, 16], [12, 100], [74, 100]]) rect(cx, cy, 2, 2, "#c3945d");
  const plate = { x: 26, y: 10, w: 36, h: 11 };
  rect(plate.x, plate.y, plate.w, plate.h, "#5b2e13"); rect(plate.x + 1, plate.y + 1, plate.w - 2, plate.h - 2, "#803f17");
  if (frame === "boards") {
    for (const [nx, ny] of [[7, 11], [79, 11], [7, 105], [79, 105], [28, 14], [58, 14]]) { rect(nx, ny, 2, 2, "#9caeb1"); set(nx + 1, ny + 1, "#5b6a70"); }
    const leaves = [[70, 4], [2, 110], [82, 60]].filter((_, i) => (seed >>> (20 + i)) % 3 !== 0 || i === 0);
    for (const [lx, ly] of leaves) {
      for (let j = 0; j < 4; j++) for (let i = 0; i < 6; i++) if (Math.abs(i - 2.5) + Math.abs(j - 1.5) * 1.6 < 3.4)
        set(lx + i, ly + j, j < 2 ? "#5dc335" : "#266627");
      rect(lx + 1, ly + 1, 4, 1, "#8ee060");
    }
  }

  // --- бюст: слои, нарисованные вручную (lib/portrait-art), раскрашиваются цветами агента ---------------------------
  const look = chibiLook(key);
  const skin = SKIN[look.skin], hair = HAIR[look.hair];
  const cloth = look.outfit === "jacket" ? CLOTH[1] : CLOTH[look.cloth], acc = CLOTH[look.accent];
  const eye = EYES[(seed >>> 7) % EYES.length];
  const color: Record<string, string> = {
    "1": skin[0], "2": skin[1], "3": skin[2], "4": shade(skin[2]), "5": skin[3],
    w: "#fdf2ea", i: eye[0], I: eye[1], p: "#2f0326", "*": "#ffffff", l: "#2f0326",
    m: "#9f2732", n: "#e7a37f", c: "#dea198",
    A: cloth[0], B: cloth[1], C: cloth[2], D: shade(shade(cloth[2])), W: "#f4f1ea", R: acc[1],
    H: hair[0], h: hair[1], d: hair[2], e: shade(hair[2]), o: hair[3],
    g: "#21140c", G: "#e8f0f0", M: "#43403f", N: "#757378",
  };
  const outfitIndex = OUTFITS.indexOf(look.outfit);
  const layers = [HAIR_BACK[look.hairStyle], BASE, OUTFIT[outfitIndex], HAIR_FRONT[look.hairStyle],
    look.accessory === "glasses" ? GLASSES : [], look.accessory === "headset" ? HEADSET : []];
  const bx = 16, by = PH - 18 - BUST_H; // низ бюста — у нижнего края панели
  let outline = 0;
  const grid: (string | null)[] = new Array(BUST_W * BUST_H).fill(null);
  for (const layer of layers) layer.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) if (row[x] !== ".") grid[y * BUST_W + x] = row[x];
  });
  for (let y = 0; y < BUST_H; y++) for (let x = 0; x < BUST_W; x++) {
    const ch = grid[y * BUST_W + x];
    const X = bx + x, Y = by + y;
    if (!ch || X < 14 || X >= 76 || Y < 18 || Y >= 102) continue; // только внутри панели
    if (ch === "5" || ch === "o" || ch === "D") outline++;
    px[Y * PW + X] = color[ch] ?? null;
  }
  return { px, plate, outline };
}

function shade(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  const f = (v: number) => Math.round(v * 0.8).toString(16).padStart(2, "0");
  return `#${f(n >> 16)}${f((n >> 8) & 255)}${f(n & 255)}`;
}
