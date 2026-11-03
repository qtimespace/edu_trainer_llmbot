import { describe, expect, it } from "vitest";
import { addStage, connect, type Flow, graph, has, moveNode, moveStage, removeStage, removeTransition, toggle } from "./flow";

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
  it("diagram: stages are nodes in a row unless moved; arrows forward, back and into Done differ", () => {
    const g = graph({ ...flow, layout: { b: { x: 500, y: 200 } } });
    expect(g.nodes.map((n) => [n.id, n.position.x, n.position.y])).toEqual(
      [["todo", 0, 0], ["a", 230, 0], ["b", 500, 200], ["done", 690, 0]]);
    expect(g.edges.map((e) => [e.id, e.kind])).toEqual(
      [["todo->a", "handoff"], ["a->b", "handoff"], ["b->done", "close"], ["b->a", "return"]]);
  });
  it("diagram edits: drag a node, draw and remove an arrow", () => {
    expect(moveNode(flow, "a", { x: 10.4, y: 19.6 }).layout).toEqual({ a: { x: 10, y: 20 } });
    expect(has(connect(flow, "a", "done"), "a", "done")).toBe(true);
    expect(connect(flow, "a", "todo")).toBe(flow);  // в «К выполнению» не возвращаемся
    expect(connect(flow, "done", "a")).toBe(flow);
    expect(connect(flow, "a", "b")).toBe(flow);  // такой переход уже есть
    expect(has(removeTransition(flow, "b", "a"), "b", "a")).toBe(false);
    expect(removeStage({ ...flow, layout: { b: { x: 1, y: 1 } } }, "b").layout).toEqual({});
  });
});
