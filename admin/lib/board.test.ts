import { describe, expect, it } from "vitest";
import { type Board, type BoardTask, columns, dot, initials, targets } from "./board";

const task = (p: Partial<BoardTask>): BoardTask => ({ id: "t", number: 1, title: "T", lesson: "L", stage: "todo",
  status: "todo", running: false, agent: { key: "devops", name: "Девопс" }, ...p });
const board: Board = {
  stages: [{ key: "todo", name: "К выполнению", agent: null }, { key: "analysis", name: "Анализ", agent: null },
    { key: "review", name: "Ревью", agent: null }, { key: "done", name: "Готово", agent: null }],
  transitions: [["todo", "analysis"], ["analysis", "review"], ["review", "analysis"], ["review", "done"]],
  tasks: [task({ id: "a", number: 1, stage: "review" }), task({ id: "b", number: 2 }), task({ id: "c", number: 3, stage: "review" })],
};

describe("board", () => {
  it("columns follow the flow, cards keep the student's order", () => {
    const cols = columns(board);
    expect(cols.map((c) => c.stage.key)).toEqual(["todo", "analysis", "review", "done"]);
    expect(cols.map((c) => c.tasks.map((t) => t.id))).toEqual([["b"], [], ["a", "c"], []]);
  });
  it("student moves along transitions; teacher anywhere but back to todo and out of done", () => {
    expect(targets(board, "review", false)).toEqual(["analysis", "done"]);
    expect(targets(board, "todo", false)).toEqual(["analysis"]);
    expect(targets(board, "todo", true)).toEqual(["analysis", "review", "done"]);
    expect(targets(board, "done", true)).toEqual([]);
  });
  it("status dot tells the student whose move it is", () => {
    expect(dot(task({ status: "waiting_student" })).label).toBe("ждёт тебя");
    expect(dot(task({ status: "in_progress", running: true })).label).toBe("агент думает");
    expect(dot(task({ status: "done", stage: "done" })).label).toBe("готово");
    expect(dot(task({})).label).toBe("не начато");
  });
  it("initials for the agent avatar", () => {
    expect(initials("Системный аналитик")).toBe("СА");
    expect(initials("CTO")).toBe("C");
    expect(initials("Веб-разработчик")).toBe("ВР");
    expect(initials("")).toBe("—");
  });
});
