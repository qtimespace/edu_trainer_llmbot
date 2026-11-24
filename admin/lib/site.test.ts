import { describe, expect, it } from "vitest";
import { type SiteInfo, siteStatus } from "./site";

const base: SiteInfo = { site_dir: null, published: false, suggested: "site-maket", url: "https://x/s/kid/" };

describe("student site status", () => {
  it("has no folder until the teacher sets one", () => expect(siteStatus(base)).toBe("nofolder"));
  it("is off with a folder but not published", () =>
    expect(siteStatus({ ...base, site_dir: "site-maket" })).toBe("off"));
  it("is on when published", () => expect(siteStatus({ ...base, site_dir: "site-maket", published: true })).toBe("on"));
});
