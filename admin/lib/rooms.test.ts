import { describe, expect, it } from "vitest";
import { bubbleFor, isDark, roomGrid, roomLayout } from "./rooms";

describe("rooms", () => {
  it("grid of rooms for group size 2..5", () => {
    expect(roomGrid(2)).toEqual({ cols: 2, rows: 1 });
    expect(roomGrid(3)).toEqual({ cols: 3, rows: 1 });
    expect(roomGrid(4)).toEqual({ cols: 2, rows: 2 });
    expect(roomGrid(5)).toEqual({ cols: 3, rows: 2 });
  });
  it("one desk and seat per agent, at most 4", () => {
    expect(roomLayout(0).seats).toEqual([]);
    const l = roomLayout(6);
    expect(l.seats).toHaveLength(4);
    expect(l.desks).toHaveLength(4);
    expect(l.seats.every((s, i) => s.x === l.desks[i].x && s.y === l.desks[i].y - 1)).toBe(true);
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
