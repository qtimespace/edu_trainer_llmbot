// Портрет агента для карточки (спека 2026-10-21-office-isometric, этап B): свой пиксельный бюст по той же внешности,
// что спрайт в офисе, в деревянной раме на звёздном фоне. Рисуется кодом; имя — HTML-подписью поверх таблички.
import { hash } from "@/lib/office";
import { type FrameStyle, PH, portraitRaster, PW } from "@/lib/portrait";
import type { Look } from "@/lib/iso";
import { colorsOf } from "./iso-sprites";

export const PORTRAIT_W = 64, PORTRAIT_H = 80;
const OUT = "#2b2118";
type Ctx = CanvasRenderingContext2D;

function ellipse(ctx: Ctx, cx: number, cy: number, rx: number, ry: number, color: string, clip?: (y: number) => boolean) {
  ctx.fillStyle = color;
  for (let y = -ry; y <= ry; y++) {
    if (clip && !clip(cy + y)) continue;
    const w = Math.round(rx * Math.sqrt(1 - (y * y) / (ry * ry)));
    ctx.fillRect(cx - w, cy + y, w * 2, 1);
  }
}
const rect = (ctx: Ctx, x: number, y: number, w: number, h: number, c: string) => { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); };

function frame(ctx: Ctx, seed: number) {
  rect(ctx, 0, 0, PORTRAIT_W, PORTRAIT_H, "#0f1d4a");
  for (let i = 0; i < 9; i++) { // звёзды
    const x = (seed >>> (i * 3)) % PORTRAIT_W, y = ((seed >>> (i * 2 + 1)) * 7 + i * 13) % PORTRAIT_H;
    rect(ctx, x, y, 1, 1, i % 3 ? "#5b7bd5" : "#e0e7ff");
  }
  const wood = "#b5652e", light = "#d4864a", dark = "#7a3e1a";
  rect(ctx, 3, 7, 58, 70, dark);
  rect(ctx, 4, 8, 56, 68, wood);
  for (let x = 6; x < 58; x += 9) rect(ctx, x, 9, 4, 1, light); // волокна
  for (let y = 12; y < 74; y += 11) { rect(ctx, 5, y, 1, 4, light); rect(ctx, 58, y + 4, 1, 4, light); }
  rect(ctx, 8, 15, 48, 58, dark);
  rect(ctx, 9, 16, 46, 56, "#e3c595"); // подложка
  rect(ctx, 9, 16, 46, 2, "#d0ae79");
  for (const [x, y] of [[6, 10], [57, 10], [6, 73], [57, 73]]) { rect(ctx, x, y, 2, 2, "#cbd5e1"); rect(ctx, x, y, 1, 1, "#f8fafc"); }
  rect(ctx, 16, 4, 32, 9, dark); // табличка для имени
  rect(ctx, 17, 5, 30, 7, "#8a4a22");
}

function bust(ctx: Ctx, look: Look) {
  const c = colorsOf(look);
  const cx = 32;
  // плечи и одежда
  for (let y = 56; y < 72; y++) { const w = 13 + Math.round((y - 56) * 0.6); rect(ctx, cx - w, y, w * 2, 1, c.t); }
  if (look.outfit === "jacket") { for (let y = 56; y < 72; y++) rect(ctx, cx - 3, y, 6, 1, c.a); rect(ctx, cx - 1, 58, 2, 10, c.r); }
  if (look.outfit === "shirt") { rect(ctx, cx - 4, 55, 3, 3, c.w); rect(ctx, cx + 1, 55, 3, 3, c.w); }
  if (look.outfit === "hoodie") { ellipse(ctx, cx, 57, 11, 3, c.a); rect(ctx, cx - 4, 60, 1, 6, c.w); rect(ctx, cx + 3, 60, 1, 6, c.w); }
  rect(ctx, cx - 4, 48, 8, 9, c.s); // шея
  // волосы сзади (длинные и каре — ниже лица)
  if (look.hairStyle === 1 || look.hairStyle === 2) ellipse(ctx, cx, look.hairStyle === 2 ? 44 : 38, 13, look.hairStyle === 2 ? 18 : 11, c.h);
  if (look.hairStyle === 3) ellipse(ctx, cx, 22, 5, 4, c.h); // пучок
  ellipse(ctx, cx, 38, 10, 12, c.s); // лицо
  // шапка волос
  const cap = look.hairStyle === 4 ? 29 : 33;
  ellipse(ctx, cx, 33, 11, 9, c.h, (y) => y <= cap);
  if (look.hairStyle === 5) { for (let i = 0; i < 6; i++) rect(ctx, cx - 9 + i, 33 + Math.floor(i / 2), 8 - i, 1, c.h); }
  if (look.hairStyle === 0) { rect(ctx, cx - 3, 23, 2, 2, c.h); rect(ctx, cx + 2, 22, 2, 3, c.h); }
  // лицо
  rect(ctx, cx - 7, 37, 4, 1, c.h); rect(ctx, cx + 3, 37, 4, 1, c.h); // брови
  for (const ex of [cx - 6, cx + 3]) { rect(ctx, ex, 39, 3, 3, c.e); rect(ctx, ex, 39, 1, 1, "#f8fafc"); }
  rect(ctx, cx - 1, 43, 2, 1, "#c98a6b"); // нос
  rect(ctx, cx - 2, 46, 4, 1, "#9a4a3a"); rect(ctx, cx - 3, 45, 1, 1, "#9a4a3a"); rect(ctx, cx + 2, 45, 1, 1, "#9a4a3a");
  rect(ctx, cx - 9, 43, 2, 1, "#f2a3a3"); rect(ctx, cx + 7, 43, 2, 1, "#f2a3a3");
  if (look.accessory === "glasses") {
    for (const ex of [cx - 8, cx + 1]) { rect(ctx, ex, 38, 7, 1, c.g); rect(ctx, ex, 42, 7, 1, c.g); rect(ctx, ex, 38, 1, 5, c.g); rect(ctx, ex + 6, 38, 1, 5, c.g); }
    rect(ctx, cx - 1, 39, 2, 1, c.g);
  }
  if (look.accessory === "headset") {
    ellipse(ctx, cx, 33, 13, 11, c.m, (y) => y <= 25);
    rect(ctx, cx - 13, 34, 3, 8, c.m); rect(ctx, cx + 10, 34, 3, 8, c.m);
    rect(ctx, cx + 10, 42, 1, 4, c.m); rect(ctx, cx + 4, 46, 7, 1, c.m);
  }
}

// контур: прозрачный пиксель рядом с фигурой становится тёмным
function outline(ctx: Ctx, w: number, h: number) {
  const img = ctx.getImageData(0, 0, w, h);
  const a = (x: number, y: number) => x >= 0 && y >= 0 && x < w && y < h && img.data[(y * w + x) * 4 + 3] > 0;
  const marks: number[] = [];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (!a(x, y) && (a(x - 1, y) || a(x + 1, y) || a(x, y - 1) || a(x, y + 1))) marks.push(x, y);
  }
  ctx.fillStyle = OUT;
  for (let i = 0; i < marks.length; i += 2) ctx.fillRect(marks[i], marks[i + 1], 1, 1);
}

export function drawPortrait(canvas: HTMLCanvasElement, key: string, look: Look) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  canvas.width = PORTRAIT_W; canvas.height = PORTRAIT_H;
  frame(ctx, hash(key));
  const fig = document.createElement("canvas");
  fig.width = PORTRAIT_W; fig.height = PORTRAIT_H;
  const f = fig.getContext("2d");
  if (!f) return;
  bust(f, look);
  outline(f, PORTRAIT_W, PORTRAIT_H);
  ctx.save();
  ctx.beginPath(); ctx.rect(9, 16, 46, 56); ctx.clip(); // фигура — внутри рамы
  ctx.drawImage(fig, 0, 0);
  ctx.restore();
}

// Портрет по арт-дирекшену (§7): растр 88×120 из lib/portrait — рама из досок или простая
export function drawPortraitRaster(canvas: HTMLCanvasElement, key: string, frame: FrameStyle) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const r = portraitRaster(key, frame);
  canvas.width = PW; canvas.height = PH;
  for (let y = 0; y < PH; y++) for (let x = 0; x < PW; x++) {
    const c = r.px[y * PW + x];
    if (!c) continue;
    ctx.fillStyle = c;
    ctx.fillRect(x, y, 1, 1);
  }
}
