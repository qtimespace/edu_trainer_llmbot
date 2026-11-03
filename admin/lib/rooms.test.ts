import { describe, expect, it } from "vitest";
import { bubbleFor, cabinAt, isDark, officePlan, type Rect, ROOM_COLS, ROOM_ROWS, roomLayout } from "./rooms";

const inside = (r: Rect, c: { x: number; y: number }) => c.x >= r.x0 && c.x < r.x1 && c.y >= r.y0 && c.y < r.y1;
const overlap = (a: Rect, b: Rect) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

describe("rooms", () => {
  it("one office floor: cabins of students on both sides of a hall that leads into the teacher's office", () => {
    const p = officePlan(5);
    expect(p.cabins).toHaveLength(5);
    const all = [p.teacher, p.hall, ...p.cabins.map((c) => c.rect)];
    all.forEach((a, i) => all.slice(i + 1).forEach((b) => expect(overlap(a, b)).toBe(false)));
    all.forEach((r) => expect(r.x0 >= 0 && r.y0 >= 0 && r.x1 <= p.cols && r.y1 <= p.rows).toBe(true));
    expect(p.hall.x0).toBe(p.teacher.x1);  // коридор упирается в кабинет преподавателя
    const wall = (x: number, y: number, axis: "x" | "y") => p.walls.some((w) => w.x === x && w.y === y && w.axis === axis);
    for (let y = p.hall.y0; y < p.hall.y1; y++) expect(wall(p.hall.x0, y, "x")).toBe(false);  // и открыт в него
    for (const c of p.cabins) {
      expect([p.hall.y0, p.hall.y1]).toContain(c.door.y);  // дверь каждого кабинета — в коридор
      expect(c.door.x >= c.rect.x0 && c.door.x < c.rect.x1).toBe(true);
      expect(wall(c.door.x, c.door.y, "y")).toBe(false);
      expect(wall(c.door.x + 1, c.door.y, "y")).toBe(true);  // а рядом с дверью — перегородка
    }
  });
  it("a single student gets one cabin next to the teacher", () => {
    const p = officePlan(1);
    expect(p.cabins).toHaveLength(1);
    expect(p.cabins[0].rect.x0).toBe(p.teacher.x1);
    expect(p.rows).toBe(p.hall.y1);
  });
  it("click on the floor finds the cabin", () => {
    const p = officePlan(4);
    const c = p.cabins[3].rect;
    expect(cabinAt(p, { x: c.x0 + 2, y: c.y0 + 3 })).toBe(3);
    expect(cabinAt(p, { x: 1, y: 1 })).toBeNull();  // кабинет преподавателя
    expect(cabinAt(p, { x: p.hall.x0 + 1, y: p.hall.y0 })).toBeNull();
  });
  it("one desk and seat per agent: the whole team of 9 fits in two rows, at most 12", () => {
    expect(roomLayout(0).seats).toEqual([]);
    const l = roomLayout(9);
    expect(l.seats).toHaveLength(9);
    expect(l.seats.every((s, i) => s.x === l.desks[i].x && s.y === l.desks[i].y - 1)).toBe(true);
    expect(new Set(l.seats.map((s) => `${s.x},${s.y}`)).size).toBe(9);  // никто не сидит друг на друге
    expect(l.desks.every((d) => d.x >= 1 && d.x < ROOM_COLS && d.y >= 1 && d.y < ROOM_ROWS - 1)).toBe(true);
    expect(roomLayout(20).seats).toHaveLength(12);
    const cab = officePlan(2).cabins[1];  // столы кабинета — внутри него
    expect(roomLayout(9, cab.rect).seats.every((s) => inside(cab.rect, s) && s.x > cab.rect.x0)).toBe(true);
  });
  it("offline room is dark", () => {
    expect(isDark({ online: false })).toBe(true);
    expect(isDark({ online: true })).toBe(false);
  });
  it("speech bubble by state", () => {
    expect(bubbleFor("waiting")).toBe("?");
    expect(bubbleFor("done")).toBe("✓");
    expect(bubbleFor("typing")).toBe("…");
    expect(bubbleFor("idle")).toBeNull();
  });
});
