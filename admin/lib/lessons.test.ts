import { describe, expect, it } from "vitest";
import { canApprove, groupByStudent, type TeacherTask } from "./lessons";

const t = (student_id: string, status: TeacherTask["status"], position = 1): TeacherTask => ({
  id: `${student_id}-${position}`, lesson_id: "l", student_id, agent_key: "devops", title: "x", statement: "",
  status, position, checks: [] });

describe("lessons", () => {
  it("groups drafts by student keeping order", () => {
    const g = groupByStudent([t("a", "draft", 1), t("b", "todo", 1), t("a", "draft", 2)]);
    expect([...g.keys()]).toEqual(["a", "b"]);
    expect(g.get("a")!.map((x) => x.position)).toEqual([1, 2]);
  });
  it("only drafts can be approved", () => {
    expect(canApprove("draft")).toBe(true);
    expect(canApprove("todo")).toBe(false);
    expect(canApprove("done")).toBe(false);
  });
});
