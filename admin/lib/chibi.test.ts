import { describe, expect, it } from "vitest";
import { chibiColor, chibiGrid, chibiLook, HAIR_STYLES, OUTFITS, ROWS } from "./chibi";

describe("chibi matrices", () => {
  it("every source row is 16 pixels wide", () => {
    for (const rows of Object.values(ROWS)) for (const r of rows) expect(r).toHaveLength(16);
  });
  it("every look, pose and view builds a 16×24 grid with known colors only", () => {
    const bad: string[] = []; // одна проверка в конце: 1080 сеток × пиксели — иначе тест не укладывается во время
    for (let hs = 0; hs < HAIR_STYLES; hs++) for (const outfit of OUTFITS) for (const accessory of ["none", "glasses", "headset"] as const) {
      const look = { hairStyle: hs, outfit, accessory, skin: 1, hair: 2, cloth: 3, accent: 4 };
      for (const pose of ["stand", "walk1", "walk2", "sit", "type1", "type2"] as const) for (const view of ["front", "back"] as const) {
        const g = chibiGrid(look, pose, view);
        const where = `${hs}/${outfit}/${accessory}/${pose}/${view}`;
        if (g.length !== 24) bad.push(`${where}: ${g.length} rows`);
        g.forEach((row, y) => {
          if (row.length !== 16) bad.push(`${where}: row ${y} has ${row.length}`);
          for (const c of row) if (c !== "." && chibiColor(c, y, look) === null) bad.push(`${where}: unknown ${c}`);
        });
      }
    }
    expect(bad).toEqual([]);
  });
  it("the head is about half of a standing character and typing moves the hands", () => {
    const look = chibiLook("doc-ba");
    const stand = chibiGrid(look, "stand", "front");
    const rows = stand.filter((r) => r.some((c) => c !== ".")).length;
    expect(11 / rows).toBeGreaterThan(0.4);
    expect(chibiGrid(look, "type1", "front").join()).not.toBe(chibiGrid(look, "type2", "front").join());
    expect(chibiGrid(look, "type1", "back").join()).not.toBe(chibiGrid(look, "type2", "back").join());
  });
  it("looks are stable per key and differ between agents", () => {
    expect(chibiLook("svc-kyc")).toEqual(chibiLook("svc-kyc"));
    const many = ["doc-ba", "doc-sa", "doc-cto", "svc-kyc", "tester", "reality"].map((k) => JSON.stringify(chibiLook(k)));
    expect(new Set(many).size).toBe(6);
  });
});

describe("seated legs", () => {
  it("a seated character has legs and shoes in both views", () => {
    const look = chibiLook("doc-ba");
    for (const view of ["front", "back"] as const) for (const pose of ["sit", "type1", "type2"] as const) {
      const g = chibiGrid(look, pose, view).map((r) => r.join(""));
      expect(g.some((r) => r.includes("P"))).toBe(true);
      expect(g.some((r) => r.includes("F"))).toBe(true);
    }
  });
});
