import { describe, expect, it } from "vitest";
import { clipboardKey } from "./clipboard";

const key = (k: string, mods: { ctrl?: boolean; shift?: boolean; meta?: boolean; type?: string; code?: string } = {}) =>
  ({ type: mods.type ?? "keydown", key: k, code: mods.code ?? `Key${k.toUpperCase()}`, ctrlKey: !!mods.ctrl,
    shiftKey: !!mods.shift, metaKey: !!mods.meta });

describe("terminal clipboard keys", () => {
  it("Ctrl+V and Ctrl+Shift+V paste (not ^V), any layout case", () => {
    expect(clipboardKey(key("v", { ctrl: true }), false)).toBe("paste");
    expect(clipboardKey(key("V", { ctrl: true, shift: true }), false)).toBe("paste");
    expect(clipboardKey(key("v", { meta: true }), false)).toBe("paste");
    expect(clipboardKey(key("м", { ctrl: true, code: "KeyV" }), false)).toBe("paste"); // русская раскладка: та же клавиша
  });
  it("Ctrl+C copies only when text is selected, otherwise it stays Ctrl+C (stop the program)", () => {
    expect(clipboardKey(key("c", { ctrl: true }), true)).toBe("copy");
    expect(clipboardKey(key("c", { ctrl: true }), false)).toBeNull();
    expect(clipboardKey(key("C", { ctrl: true, shift: true }), false)).toBe("copy");
  });
  it("other keys and keyup go to the terminal as usual", () => {
    expect(clipboardKey(key("v"), false)).toBeNull();
    expect(clipboardKey(key("x", { ctrl: true }), true)).toBeNull();
    expect(clipboardKey(key("v", { ctrl: true, type: "keyup" }), false)).toBeNull();
  });
});
