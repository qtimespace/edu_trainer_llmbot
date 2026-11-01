import { describe, expect, it } from "vitest";
import { bfs, buildLayout, bubbleFor, frameFor, newlyWaiting, palette, type OfficeDesk } from "./office";

const desk = (id: string, n: number): OfficeDesk => ({
  kind: "discussion", kind_label: "обсуждение", id, iid: id, title: "", status: "analysis", mine: true,
  url: `/discussions/${id}`, spent_usd: 0, budget_usd: 1, final: false, waiting: null, blocked: null,
  agents: Array.from({ length: n }, (_, i) => ({ key: `a${i}`, stage: "analyst", model: "", state: "typing",
    last: null })),
});

describe("office layout", () => {
  it("gives every agent of every desk its own seat and keeps desks apart", () => {
    const layout = buildLayout([desk("d1", 6), desk("d2", 3), desk("d3", 8)]);
    const seats = layout.desks.flatMap((d) => d.seats.map((s) => `${s.x},${s.y}`));
    expect(new Set(seats).size).toBe(17);
    const [a, b] = layout.desks;
    expect(a.box.x + a.box.w <= b.box.x || a.box.y + a.box.h <= b.box.y).toBe(true);
  });
  it("a team bigger than one desk continues at the next desk, nobody is drawn twice or lost", () => {
    const layout = buildLayout([desk("d1", 10)]);
    const keys = layout.desks.flatMap((d) => d.agents.map((a) => a.key));
    expect(keys).toEqual(Array.from({ length: 10 }, (_, i) => `a${i}`));
    expect(layout.desks.every((d) => d.agents.length === d.seats.length)).toBe(true);
  });
  it("grows downwards with many desks and stays a valid grid", () => {
    const layout = buildLayout(Array.from({ length: 21 }, (_, i) => desk(`d${i}`, 4)));
    expect(layout.rows).toBeGreaterThan(30);
    expect(layout.walkable.length).toBe(layout.rows);
    expect(layout.walkable[0].length).toBe(layout.cols);
  });
  it("an empty office still has a lounge to wander in", () => {
    const layout = buildLayout([]);
    expect(layout.lounge.length).toBeGreaterThan(4);
    expect(layout.lounge.every((p) => layout.walkable[p.y][p.x])).toBe(true);
  });
});

describe("office characters", () => {
  it("an agent always looks the same and two agents look different", () => {
    expect(palette("doc-ba")).toEqual(palette("doc-ba"));
    expect(palette("doc-ba").shirt).not.toBe(palette("doc-sa").shirt);
  });
  it("typing and reading animate, waiting does not hide behind a frame", () => {
    expect(frameFor("typing", 0)).not.toBe(frameFor("typing", 300));
    expect(frameFor("reading", 0)).not.toBe(frameFor("reading", 700));
    expect(frameFor("waiting", 0)).toBe("sit");
    expect(frameFor("typing", 300, true)).toBe(frameFor("typing", 0, true));  // reduced motion
  });
  it("bubbles say who needs a person, who is blocked or failed", () => {
    expect(bubbleFor("waiting")?.icon).toBe("?");
    expect(bubbleFor("error")?.icon).toBe("!");
    expect(bubbleFor("done")?.icon).toBe("✓");
    expect(bubbleFor("typing")).toBeNull();
  });
  it("rings only for desks that started waiting since the last poll", () => {
    const w = { ...desk("d1", 1), waiting: { reason: "вопросы", url: "/discussions/d1" } };
    expect(newlyWaiting(null, [w])).toEqual([]);  // первая загрузка — без звука
    expect(newlyWaiting(new Set(), [w, desk("d2", 1)])).toEqual(["discussion:d1"]);
    expect(newlyWaiting(new Set(["discussion:d1"]), [w])).toEqual([]);
  });
  it("finds a walking path around obstacles", () => {
    const grid = [
      [true, true, true],
      [false, false, true],
      [true, true, true],
    ];
    const path = bfs(grid, { x: 0, y: 0 }, { x: 0, y: 2 });
    expect(path?.length).toBe(7);
    expect(bfs(grid, { x: 0, y: 0 }, { x: 0, y: 1 })).toBeNull();
  });
});
