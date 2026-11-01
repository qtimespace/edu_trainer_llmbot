import { describe, expect, it } from "vitest";
import { homeFor, menuFor } from "./nav";

describe("menuFor", () => {
  it("student sees only own room, no teacher screens", () => {
    const labels = menuFor("student").map((i) => i.label);
    expect(labels).toEqual(["Моя комната"]);
    expect(labels).not.toContain("Группа");
  });
  it("teacher sees office, group, lessons and settings", () => {
    expect(menuFor("teacher").map((i) => i.href)).toEqual(["/office", "/group", "/lessons", "/settings/llm",
      "/settings/agents"]);
  });
  it("home page depends on role", () => {
    expect(homeFor("student")).toBe("/room");
    expect(homeFor("teacher")).toBe("/office");
  });
});
