import { describe, expect, it } from "vitest";
import { clock, dayBreaks, failedCount, prompt, reviewTab } from "./review";

describe("review", () => {
  it("unknown tab falls back to the board", () => {
    expect(reviewTab("console")).toBe("console");
    expect(reviewTab("nope")).toBe("board");
    expect(reviewTab(null)).toBe("board");
  });

  it("shows where the command was typed", () => {
    expect(prompt("lobby")).toBe("lobby$");
    expect(prompt("student")).toBe("student@lab$");
  });

  it("no timestamp in history — a dash instead of 1970", () => {
    expect(clock(0)).toBe("—");
    expect(clock(1700000100)).toMatch(/\d{2}:\d{2}:\d{2}/);
  });

  it("marks the first command of each day", () => {
    const day = 86400;
    const items = [{ at: 1700000100, where: "lobby" as const, cmd: "ls" },
      { at: 1700000200, where: "student" as const, cmd: "pwd" },
      { at: 1700000100 + day, where: "student" as const, cmd: "cd" }];
    expect([...dayBreaks(items)]).toEqual([0, 2]);
  });

  it("counts failed checks", () => {
    expect(failedCount({ files: [], checks: [{ about: "a", cmd: "x", passed: true, output: "" },
      { about: "b", cmd: "y", passed: false, output: "" }] })).toBe(1);
  });
});
