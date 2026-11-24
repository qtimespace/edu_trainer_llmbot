import { describe, expect, it } from "vitest";
import { decodeChunk, parseSize } from "./screen";

describe("terminal screen replay", () => {
  it("decodes base64 output to bytes, Cyrillic included", () => {
    const b64 = Buffer.from("ls\r\nфайл.txt\r\n").toString("base64");
    expect(new TextDecoder().decode(decodeChunk(b64))).toBe("ls\r\nфайл.txt\r\n");
  });
  it("reads the student's window size and rejects junk", () => {
    expect(parseSize(Buffer.from("120x30").toString("base64"))).toEqual({ cols: 120, rows: 30 });
    expect(parseSize(Buffer.from("abc").toString("base64"))).toBeNull();
    expect(parseSize(Buffer.from("0x30").toString("base64"))).toBeNull();
  });
});
