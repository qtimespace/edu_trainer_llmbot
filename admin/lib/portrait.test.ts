import { describe, expect, it } from "vitest";
import { PW, PH, portraitRaster } from "./portrait";

const at = (r: ReturnType<typeof portraitRaster>, x: number, y: number) => r.px[y * PW + x];

describe("portrait raster", () => {
  it("is 88×120 with a frame, a starry background and a plate for the name", () => {
    const r = portraitRaster("doc-ba", "boards");
    expect(r.px).toHaveLength(PW * PH);
    expect(at(r, 1, 60)).toBe("#041742"); // фон слева от рамы
    expect(r.px.filter((c) => c === "#cc683d").length).toBeGreaterThan(400); // доски рамы
    expect(r.plate).toEqual({ x: 26, y: 10, w: 36, h: 11 });
  });
  it("draws eyes with white, iris, pupil and a highlight", () => {
    const r = portraitRaster("doc-ba", "boards");
    const face = r.px.slice(44 * PW, 54 * PW);
    expect(face).toContain("#fdf2ea"); // белок
    expect(face).toContain("#ffffff"); // блик
    expect(face).toContain("#2f0326"); // ресницы и зрачок
  });
  it("outlines the figure and is stable per key, different between agents", () => {
    const a = portraitRaster("doc-ba", "boards"), b = portraitRaster("svc-kyc", "boards");
    expect(a.px.join()).toBe(portraitRaster("doc-ba", "boards").px.join());
    expect(a.px.join()).not.toBe(b.px.join());
    expect(a.outline).toBeGreaterThan(100);
  });
  it("the simple frame keeps the same bust", () => {
    const boards = portraitRaster("doc-ba", "boards"), simple = portraitRaster("doc-ba", "simple");
    // лицо одинаковое: та же внешность, другой только окрас рамы
    const panel = (r: typeof boards) => Array.from({ length: 10 }, (_, j) => r.px.slice((44 + j) * PW + 14, (44 + j) * PW + 76).join()).join("|");
    expect(panel(boards)).toBe(panel(simple));
  });
});

describe("hand-drawn bust layers", () => {
  it("every layer is empty or 80 rows of at most 56 legend characters", async () => {
    const art = await import("./portrait-art");
    const legal = new Set(".12345wiIp*lmncABCDWRHhdeogGMN".split(""));
    const layers = [art.BASE, ...art.HAIR_BACK, ...art.HAIR_FRONT, ...art.OUTFIT, art.GLASSES, art.HEADSET];
    expect(art.HAIR_BACK).toHaveLength(6);
    expect(art.HAIR_FRONT).toHaveLength(6);
    expect(art.OUTFIT).toHaveLength(5);
    const bad = layers.flatMap((l, n) => l.length === 0 ? [] : l.length !== 80 ? [`${n}: ${l.length} rows`]
      : l.flatMap((r, y) => r.length > 56 || [...r].some((c) => !legal.has(c)) ? [`${n}:${y}`] : []));
    expect(bad).toEqual([]);
  });
});
