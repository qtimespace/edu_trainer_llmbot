import { describe, expect, it } from "vitest";
import { addStage, type Flow, has, moveStage, removeStage, toggle } from "./flow";

const flow: Flow = {
  stages: [{ key: "todo", name: "К выполнению", agent_key: null }, { key: "a", name: "A", agent_key: null },
    { key: "b", name: "B", agent_key: "techlead" }, { key: "done", name: "Готово", agent_key: null }],
  transitions: [["todo", "a"], ["a", "b"], ["b", "done"], ["b", "a"]],
};

describe("flow editor", () => {
  it("adds a stage before Done with a fresh key", () => {
    const f = addStage(flow);
    expect(f.stages.map((s) => s.key)).toEqual(["todo", "a", "b", "stage-1", "done"]);
    expect(addStage(f).stages[4].key).toBe("stage-2");
  });
  it("removing a stage drops its transitions", () => {
    const f = removeStage(flow, "b");
    expect(f.stages.map((s) => s.key)).toEqual(["todo", "a", "done"]);
    expect(f.transitions).toEqual([["todo", "a"]]);
  });
  it("middle stages move, but never past the fixed first and last", () => {
    expect(moveStage(flow, "b", -1).stages.map((s) => s.key)).toEqual(["todo", "b", "a", "done"]);
    expect(moveStage(flow, "a", -1)).toBe(flow);
    expect(moveStage(flow, "b", 1)).toBe(flow);
  });
  it("toggles a transition", () => {
    expect(has(toggle(flow, "a", "done"), "a", "done")).toBe(true);
    expect(has(toggle(flow, "b", "a"), "b", "a")).toBe(false);
  });
});
