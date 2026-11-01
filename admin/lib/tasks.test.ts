import { describe, expect, it } from "vitest";
import { canSend, canStart, statusLabel, wsUrl } from "./tasks";

describe("student tasks", () => {
  it("labels for students", () => {
    expect(statusLabel("todo")).toBe("к выполнению");
    expect(statusLabel("waiting_student")).toBe("ждёт тебя");
    expect(statusLabel("done")).toBe("готово");
  });
  it("can send only while working and agent is not thinking", () => {
    expect(canSend("waiting_student", false)).toBe(true);
    expect(canSend("waiting_student", true)).toBe(false);
    expect(canSend("done", false)).toBe(false);
    expect(canSend("todo", false)).toBe(false);
    expect(canStart("todo")).toBe(true);
    expect(canStart("in_progress")).toBe(false);
  });
  it("terminal websocket url", () => {
    expect(wsUrl({ protocol: "https:", host: "trainer.example.ru" }, undefined)).toBe("wss://trainer.example.ru/ws/terminal");
    expect(wsUrl({ protocol: "http:", host: "localhost:3000" }, undefined)).toBe("ws://localhost:3000/ws/terminal");
    expect(wsUrl({ protocol: "http:", host: "localhost:3000" }, "ws://127.0.0.1:8000")).toBe("ws://127.0.0.1:8000/ws/terminal");
  });
});
