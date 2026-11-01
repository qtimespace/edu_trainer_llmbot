import { describe, expect, it } from "vitest";
import { safeNext } from "./redirect";

const ORIGIN = "http://localhost:3000";

describe("safeNext", () => {
  it("keeps paths inside the panel", () => {
    expect(safeNext("/tasks/885?tab=log#x", ORIGIN)).toBe("/tasks/885?tab=log#x");
    expect(safeNext(null, ORIGIN)).toBe("/");
  });

  it("rejects anything that leaves the origin", () => {
    for (const bad of ["//evil.com", "/\\evil.com", "/\t/evil.com", "/\n/evil.com", "https://evil.com",
      "javascript:alert(1)", "evil.com", "\\\\evil.com", "/.//evil.com", "/..//evil.com", "/a/..//evil.com",
      "/%2e//evil.com"]) {
      expect(safeNext(bad, ORIGIN)).toBe("/");
    }
  });
});
