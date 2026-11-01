import { describe, expect, it } from "vitest";
import { seatsView, sizeOptions } from "./group";

describe("group", () => {
  it("group size is 2..5", () => expect(sizeOptions()).toEqual([2, 3, 4, 5]));
  it("shows empty seats up to group size", () => {
    const seats = seatsView(3, [{ seat: 2, name: "Маша" }]);
    expect(seats.map((s) => s.student?.name ?? null)).toEqual([null, "Маша", null]);
  });
});
