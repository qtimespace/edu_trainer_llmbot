import { describe, expect, it } from "vitest";
import { bfs, type OfficeAgent, type OfficeDesk } from "./office";
import { agentStatus, buildIsoLayout, buildRosterLayout, depthOrder, layoutShape, look, pickReplies, plaqueLabelAt, replyFor, seatId, TH, toGrid,
  toScreen, TW } from "./iso";

const agentOf = (key: string, state: OfficeAgent["state"] = "typing", detail = ""): OfficeAgent =>
  ({ key, stage: "analyst", model: "", state, last: detail ? { outcome: "error", detail, at: "" } : null });
const desk = (id: string, n: number, over: Partial<OfficeDesk> = {}): OfficeDesk => ({
  kind: "discussion", kind_label: "обсуждение", id, iid: id, title: "", status: "analysis", mine: true,
  url: `/discussions/${id}`, spent_usd: 0, budget_usd: 1, final: false, waiting: null, blocked: null,
  agents: Array.from({ length: n }, (_, i) => agentOf(`${id}-a${i}`)), ...over,
});

describe("projection", () => {
  it("maps a grid cell to the screen and back", () => {
    const o = { ox: 200, oy: 40 };
    for (const [x, y] of [[0, 0], [3, 7], [12, 2]]) {
      const s = toScreen(x, y, o);
      expect(toGrid(s.x + 1, s.y + TH / 2, o)).toEqual({ x, y });  // точка внутри ромба клетки
    }
    expect(toScreen(1, 0, { ox: 0, oy: 0 })).toEqual({ x: TW / 2, y: TH / 2 });
  });
  it("draws farther cells first and things above the floor after their floor", () => {
    const items = [{ x: 2, y: 2, layer: 0, id: "c" }, { x: 0, y: 0, layer: 1, id: "a" }, { x: 2, y: 2, layer: 1, id: "d" },
      { x: 1, y: 0, layer: 1, id: "b" }];
    expect(depthOrder(items).map((i) => i.id)).toEqual(["a", "b", "c", "d"]);
  });
});

describe("iso layout", () => {
  it("seats every agent once, a team over 8 continues at a second island of the same run", () => {
    const layout = buildIsoLayout([desk("d1", 10), desk("d2", 3)]);
    const keys = layout.islands.flatMap((i) => i.agents.map((a) => a.key));
    expect(keys).toHaveLength(13);
    expect(new Set(keys).size).toBe(13);
    expect(layout.islands.filter((i) => i.desk.id === "d1")).toHaveLength(2);
    const seats = layout.islands.flatMap((i) => i.seats.map((s) => `${s.x},${s.y}`));
    expect(new Set(seats).size).toBe(13);
  });
  it("islands do not overlap and every seat faces its own monitor on a desk cell", () => {
    const layout = buildIsoLayout(Array.from({ length: 5 }, (_, i) => desk(`d${i}`, 8)));
    const cells = layout.islands.flatMap((i) => i.deskCells.map((c) => `${c.x},${c.y}`));
    expect(new Set(cells).size).toBe(cells.length);
    for (const island of layout.islands) {
      for (const s of island.seats) {
        expect(island.deskCells.some((c) => c.x === s.monitor.x && c.y === s.monitor.y)).toBe(true);
        expect(Math.abs(s.monitor.x - s.x) + Math.abs(s.monitor.y - s.y)).toBe(1);
      }
    }
  });
  it("the lounge is reachable from every island and has sofa seats; an empty office is just the lounge", () => {
    const layout = buildIsoLayout(Array.from({ length: 21 }, (_, i) => desk(`d${i}`, 4)));
    const target = layout.lounge[0];
    for (const island of layout.islands) {
      const start = island.aisle;
      expect(bfs(layout.walkable, start, target)).not.toBeNull();
    }
    const empty = buildIsoLayout([]);
    expect(empty.islands).toEqual([]);
    expect(empty.sofaSeats.length).toBeGreaterThanOrEqual(2);
    expect(empty.furniture.map((f) => f.kind)).toEqual(expect.arrayContaining(["sofa", "vending", "plant", "aquarium"]));
    expect(empty.lounge.every((p) => empty.walkable[p.y][p.x])).toBe(true);
  });
});

describe("replies", () => {
  it("speaks by state and the last error", () => {
    const d = desk("d1", 1, { waiting: { reason: "вопросы", url: "/discussions/d1" } });
    expect(replyFor(agentOf("a", "waiting"), d, 0)).toMatchObject({ text: "Нужен ответ!", sticky: true,
      href: "/discussions/d1" });
    expect(replyFor(agentOf("a", "error", "429 Too Many Requests"), d, 0)?.text).toBe("429, жду…");
    expect(replyFor(agentOf("a", "error", "rate_limited: модели на паузе"), d, 0)?.text).toBe("429, жду…");
    expect(replyFor(agentOf("a", "error", "не хватает бюджета"), d, 0)?.text).toBe("Кончился бюджет");
    expect(replyFor(agentOf("a", "error", "boom"), d, 0)?.text).toBe("Ошибка!");
    expect(replyFor(agentOf("a", "done"), d, 0)?.text).toBe("Готово!");
    expect(replyFor(agentOf("a", "seated"), d, 0)).toBeNull();
  });
  it("typing and reading talk only now and then, not all at once", () => {
    const d = desk("d1", 1);
    const said = Array.from({ length: 50 }, (_, t) => replyFor(agentOf("a", "typing"), d, t * 4000)).filter(Boolean);
    expect(said.length).toBeGreaterThan(0);
    expect(said.length).toBeLessThan(25);
    expect(said[0]?.text).toBe("Пишу…");
  });
  it("the first agent of a desk waiting for documents says so", () => {
    const d = desk("d1", 2, { status: "waiting_docs", blocked: { icon: "📄", reason: "ждём документы" } });
    expect(replyFor(d.agents[0], d, 0)?.text).toBe("Ждём документы");
    expect(replyFor({ ...d.agents[1], state: "seated" }, d, 0)).toBeNull();
  });
  it("keeps every waiting reply and at most three others, errors first", () => {
    const r = (text: string, sticky = false, priority = 1) => ({ text, tone: "", sticky, priority });
    const picked = pickReplies([
      { key: "w1", reply: r("Нужен ответ!", true, 0) }, { key: "w2", reply: r("Нужен ответ!", true, 0) },
      { key: "t1", reply: r("Пишу…", false, 3) }, { key: "e1", reply: r("Ошибка!", false, 1) },
      { key: "t2", reply: r("Пишу…", false, 3) }, { key: "d1", reply: r("Готово!", false, 2) },
      { key: "t3", reply: r("Проверяю…", false, 3) },
    ]);
    expect(picked.map((p) => p.key)).toEqual(["w1", "w2", "e1", "d1", "t1"]);
  });
});

describe("look", () => {
  it("an agent looks the same everywhere and agents differ", () => {
    expect(look("doc-ba")).toEqual(look("doc-ba"));
    const looks = ["doc-ba", "doc-sa", "doc-cto", "svc-kyc", "tester", "reality"].map((k) => JSON.stringify(look(k)));
    expect(new Set(looks).size).toBe(6);
    const l = look("doc-ba");
    expect(l.hairStyle).toBeGreaterThanOrEqual(0);
    expect(l.hairStyle).toBeLessThan(6);
    expect(["shirt", "jacket", "hoodie"]).toContain(l.outfit);
    expect(["none", "glasses", "headset"]).toContain(l.accessory);
  });
});

describe("review fixes", () => {
  it("a member swapped at the same team size changes the layout shape", () => {
    const a = desk("d1", 2);
    const b = { ...a, agents: [a.agents[0], agentOf("newcomer")] };
    expect(layoutShape([a])).not.toBe(layoutShape([b]));
    expect(layoutShape([a])).toBe(layoutShape([{ ...a, status: "verification" }]));  // смена статуса — та же раскладка
  });
  it("the plaque label sits below the faces of its island", () => {
    const o = { ox: 300, oy: 60 };
    for (const island of buildIsoLayout([desk("d1", 8), desk("d2", 8)]).islands) {
      const label = plaqueLabelAt(island, o);
      for (const s of island.seats) expect(label.y).toBeGreaterThanOrEqual(toScreen(s.x, s.y, o).y + TH / 2);
    }
  });
});

describe("the same agent twice in a run", () => {
  it("gets two seats with their own place in the run, so each keeps its own state", () => {
    const d = desk("d1", 0, { agents: [agentOf("doc-ba", "typing"), agentOf("doc-ba", "error", "429"),
      ...Array.from({ length: 8 }, (_, i) => agentOf(`x${i}`))] });
    const islands = buildIsoLayout([d]).islands;
    expect(islands.map((i) => i.offset)).toEqual([0, 8]);
    const ids = islands.flatMap((i) => i.agents.map((_, s) => seatId(i, s)));
    expect(new Set(ids).size).toBe(10);
    expect(islands[0].agents[1].state).toBe("error");
  });
});

describe("GDS seating along x", () => {
  it("near row looks at -x, far row at +x, each next to its own monitor; nobody lost", () => {
    const layout = buildIsoLayout([desk("d1", 8), desk("d2", 3)], "x");
    const seats = layout.islands.flatMap((i) => i.seats);
    expect(seats).toHaveLength(11);
    expect(new Set(seats.map((s) => `${s.x},${s.y}`)).size).toBe(11);
    for (const island of layout.islands) {
      for (const s of island.seats) {
        expect(["W", "E"]).toContain(s.facing);
        expect(s.monitor.y).toBe(s.y);
        expect(s.monitor.x).toBe(s.facing === "W" ? s.x - 1 : s.x + 1);
        expect(island.deskCells.some((c) => c.x === s.monitor.x && c.y === s.monitor.y)).toBe(true);
      }
    }
    const target = layout.lounge[0];
    for (const island of layout.islands) expect(bfs(layout.walkable, island.aisle, target)).not.toBeNull();
  });
});

describe("room zones", () => {
  it("adds lobby, lead desk and lounge along the walls without blocking islands or the way to the lounge", () => {
    for (const n of [0, 3, 9]) {
      const layout = buildIsoLayout(Array.from({ length: n }, (_, i) => desk(`d${i}`, 6)), "y", "zones");
      const kinds = new Set(layout.furniture.map((f) => f.kind));
      for (const k of ["reception", "cabinet", "leaddesk", "partition", "vending", "sofa", "aquarium"]) expect(kinds).toContain(k);
      const islandCells = new Set(layout.islands.flatMap((i) => [...i.deskCells, ...i.seats, i.plaque].map((c) => `${c.x},${c.y}`)));
      for (const f of layout.furniture) {
        expect(islandCells.has(`${f.x},${f.y}`)).toBe(false);
        expect(f.x).toBeLessThan(layout.cols);
        expect(f.y).toBeLessThan(layout.rows);
      }
      expect(layout.sofaSeats.length).toBeGreaterThanOrEqual(2);
      const target = layout.lounge[0];
      for (const island of layout.islands) expect(bfs(layout.walkable, island.aisle, target)).not.toBeNull();
      expect(layout.lounge.every((p) => layout.walkable[p.y][p.x])).toBe(true);
    }
  });
});

describe("own desk for every agent", () => {
  const roster = [
    ...Array.from({ length: 10 }, (_, i) => ({ key: `doc-${i}`, name: `Doc ${i}`, kind: "author" })),
    { key: "testing-a", name: "T", kind: "verifier" }, { key: "svc-kyc", name: "kyc", kind: "owner" },
    { key: "doc-cto", name: "CTO", kind: "orchestrator" },
  ];
  it("seats every project agent once, grouped into departments by kind, plus guests from runs", () => {
    const layout = buildRosterLayout(roster, ["stranger"], "y", "zones");
    const keys = layout.islands.flatMap((i) => i.agents.map((a) => a.key));
    expect(keys.sort()).toEqual([...roster.map((r) => r.key), "stranger"].sort());
    const dept = (k: string) => layout.islands.find((i) => i.agents.some((a) => a.key === k))!.desk.kind_label;
    expect(dept("doc-3")).toBe("Аналитики и писатели");
    expect(dept("testing-a")).toBe("Проверяющие");
    expect(dept("svc-kyc")).toBe("Сервисы");
    expect(dept("doc-cto")).toBe("Руководство");
    expect(dept("stranger")).toBe("Гости");
    expect(layout.islands.filter((i) => i.desk.kind_label === "Аналитики и писатели")).toHaveLength(2); // 10 > 8
    const target = layout.lounge[0];
    for (const island of layout.islands) expect(bfs(layout.walkable, island.aisle, target)).not.toBeNull();
  });
  it("an agent in several runs (or twice in one) shows its most important state and lists its runs", () => {
    const a = desk("d1", 0, { agents: [agentOf("doc-1", "typing"), agentOf("doc-1", "seated")] });
    const b = desk("d2", 0, { iid: "885", agents: [agentOf("doc-1", "waiting")],
      waiting: { reason: "вопросы", url: "/discussions/d2" } });
    const status = agentStatus([a, b]);
    expect(status.get("doc-1")!.agent.state).toBe("waiting");
    expect(status.get("doc-1")!.desk.id).toBe("d2");
    expect(status.get("doc-1")!.runs.map((d) => d.id)).toEqual(["d2", "d1"]);
    expect(status.has("doc-2")).toBe(false);
  });
});
