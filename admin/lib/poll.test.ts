import { describe, expect, it } from "vitest";
import { nextPoll } from "./poll";

const until = (d: { status: string }) => d.status === "done";

describe("nextPoll", () => {
  it("polls while the run is in progress and stops where a person acts", () => {
    expect(nextPoll({ pollMs: 5000, data: { status: "writing" }, failures: 0, until })).toBe(5000);
    expect(nextPoll({ pollMs: 5000, data: { status: "done" }, failures: 0, until })).toBeNull();
    expect(nextPoll({ pollMs: undefined, data: { status: "writing" }, failures: 0, until })).toBeNull();
  });

  it("keeps retrying after a failed poll with backoff instead of stopping for good", () => {
    expect(nextPoll({ pollMs: 5000, data: { status: "writing" }, failures: 1, until })).toBe(10000);
    expect(nextPoll({ pollMs: 5000, data: { status: "writing" }, failures: 5, until })).toBe(60000);
    expect(nextPoll({ pollMs: 5000, data: null, failures: 1, until })).toBe(10000);
  });
});
