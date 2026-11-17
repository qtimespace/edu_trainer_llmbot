import { describe, expect, it } from "vitest";
import { duration, focusShare, pageState, plateSuffix } from "./attention";

describe("attention", () => {
  it("hidden tab wins over focus; otherwise focus decides", () => {
    expect(pageState("hidden", true)).toBe("hidden");
    expect(pageState("visible", true)).toBe("focused");
    expect(pageState("visible", false)).toBe("blurred");
  });

  it("durations read like a person would say them", () => {
    expect(duration(0)).toBe("0 мин");
    expect(duration(20)).toBe("<1 мин");
    expect(duration(12 * 60 + 5)).toBe("12 мин");
    expect(duration(65 * 60)).toBe("1 ч 5 мин");
  });

  it("plate shows where the student is looking and for how long", () => {
    const now = Date.parse("2026-11-17T10:10:00Z");
    expect(plateSuffix(false, undefined, now)).toBe(" · не в сети");
    expect(plateSuffix(true, { state: "focused", since: "2026-11-17T10:00:00Z" }, now)).toBe(" · смотрит");
    expect(plateSuffix(true, { state: "hidden", since: "2026-11-17T10:05:00Z" }, now)).toBe(" · вкладка скрыта 5 мин");
    expect(plateSuffix(true, undefined, now)).toBe("");  // старая вкладка без состояния — просто в сети
  });

  it("focus share counts only time online", () => {
    expect(focusShare({ focused: 30, blurred: 10, hidden: 60 })).toBe(30);
    expect(focusShare({ focused: 0, blurred: 0, hidden: 0 })).toBeNull();
  });
});
