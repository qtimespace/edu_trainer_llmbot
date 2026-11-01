import { describe, expect, it } from "vitest";
import { modelBody, modelKey } from "./llm";

describe("llm catalog", () => {
  it("model key is provider/name with safe characters", () => {
    expect(modelKey("openrouter", "qwen/qwen3-coder:free")).toBe("openrouter/qwen-qwen3-coder:free");
    expect(modelKey("hf", "deepseek-ai/DeepSeek V4")).toBe("hf/deepseek-ai-DeepSeek-V4");
  });
  it("model body from provider offer", () => {
    expect(modelBody("hf", { model: "x/y", name: "Y", context_window: 1000, pricing: { input: 1, output: 2 } }))
      .toEqual({ provider: "hf", model: "x/y", capabilities: ["reasoning"], context_window: 1000,
        pricing: { input: 1, output: 2 } });
  });
});
