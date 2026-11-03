"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChibiPose } from "@/lib/chibi";
import { depthOrder, type Facing, TH, toGrid, toScreen, TW } from "@/lib/iso";
import { bubbleFor, cabinAt, type Cell, isDark, type Office, officePlan, type Rect, roomLayout,
  type RoomAgent, STATE_LABEL } from "@/lib/rooms";
import { BG, chairBack, chairSeat, CHAR_H, CHAR_W, desk, drawChibi, fillPoly, floorTile, furniture, monitor,
  partition, slab, SLAB_H, WALL_H, wallBack, wallSide } from "./iso-sprites";

const PAD = 6;
const RENDER_MS = 150;
const FACING: Facing = "S";
const TEACHER = { seat: { x: 4, y: 3 }, desk: { x: 4, y: 4 } };
type Item = { x: number; y: number; layer: number; draw: (g: CanvasRenderingContext2D, sx: number, sy: number) => void };
// клетка → левый верх спрайта сидящего персонажа
const charAt = (s: { x: number; y: number }) => ({ x: s.x - CHAR_W / 2, y: s.y + TH / 2 - 23 });
const inRect = (r: Rect, x: number, y: number) => x >= r.x0 && x < r.x1 && y >= r.y0 && y < r.y1;

function pose(a: RoomAgent, ms: number, i: number): ChibiPose {
  if (a.state !== "typing") return "sit";
  return Math.floor((ms + i * 130) / 250) % 2 ? "type1" : "type2";
}

// сидящий за столом лицом к зрителю: кресло, персонаж, стол с монитором
function seated(items: Item[], key: string, seat: Cell, d: Cell, poseAt: (ms: number) => ChibiPose, glow: () => boolean,
  ms: number) {
  items.push({ x: seat.x, y: seat.y, layer: 0, draw: (g, sx, sy) => chairBack(g, sx, sy, FACING) });
  items.push({ x: seat.x, y: seat.y, layer: 1, draw: (g, sx, sy) => chairSeat(g, sx, sy) });
  items.push({ x: seat.x, y: seat.y, layer: 2, draw: (g, sx, sy) => {
    const p = charAt({ x: sx, y: sy });
    drawChibi(g, key, poseAt(ms), "front", p.x, p.y, false);
  } });
  items.push({ x: d.x, y: d.y, layer: 1, draw: (g, sx, sy) => { desk(g, sx, sy); monitor(g, sx, sy, FACING, glow(), ms); } });
}

// Офис группы одним этажом: кабинет преподавателя слева, от него коридор, по обе стороны — кабинеты учеников.
// Кабинет ученика не в сети — без света и без агентов. Масштаб — по ширине контейнера.
export function RoomsOffice({ office, onAgent, selected, onRoom }: { office: Office;
  onAgent?: (studentId: string, a: RoomAgent) => void; selected?: string | null; onRoom?: (studentId: string) => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [scale, setScale] = useState(1);
  const [reduced, setReduced] = useState(false);
  const plan = useMemo(() => officePlan(office.rooms.length), [office.rooms.length]);
  const W = (plan.cols + plan.rows) * (TW / 2) + 2 * PAD;
  const H = (plan.cols + plan.rows) * (TH / 2) + WALL_H + SLAB_H + 2 * PAD;
  const origin = useMemo(() => ({ ox: plan.rows * (TW / 2) + PAD, oy: WALL_H + PAD }), [plan.rows]);
  const live = useRef({ office, selected });
  live.current = { office, selected };

  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    const el = wrap.current;
    if (!el) return;
    const fit = () => setScale(Math.max(1, Math.min(3, Math.floor(el.clientWidth / W))));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, [W]);

  useEffect(() => {
    const view = canvas.current?.getContext("2d");
    if (!view) return;
    const base = document.createElement("canvas");
    base.width = W; base.height = H;
    const ctx = base.getContext("2d");
    if (!ctx) return;
    const at = (x: number, y: number) => toScreen(x, y, origin);
    const area = (r: Rect) => [at(r.x0, Math.max(1, r.y0)), at(r.x1, Math.max(1, r.y0)), at(r.x1, r.y1), at(r.x0, r.y1)]
      .map((p) => [p.x, p.y] as [number, number]);
    let raf = 0, last = -RENDER_MS;

    const draw = (ms: number) => {
      const { office: o, selected: sel } = live.current;
      const t = reduced ? 0 : ms;
      ctx.fillStyle = BG;
      ctx.fillRect(0, 0, W, H);
      for (let y = 1; y < plan.rows; y++) for (let x = 1; x < plan.cols; x++) {
        const s = at(x, y), hall = inRect(plan.hall, x, y) || !plan.cabins.some((c) => inRect(c.rect, x, y));
        floorTile(ctx, s.x, s.y, hall ? ((x + y) % 2 ? "tile" : "tile2") : (x + y) % 2 ? "wood" : "wood2");
      }
      for (let x = 1; x < plan.cols; x++) { const s = at(x, plan.rows - 1); slab(ctx, s.x, s.y, "y"); }
      for (let y = 1; y < plan.rows; y++) { const s = at(plan.cols - 1, y); slab(ctx, s.x, s.y, "x"); }
      for (let x = 0; x < plan.cols; x++) { const s = at(x, 0); wallBack(ctx, s.x, s.y, x); }
      for (let y = 1; y < plan.rows; y++) { const s = at(0, y); wallSide(ctx, s.x, s.y, y); }

      const items: Item[] = plan.walls.map((w) => ({ x: w.x, y: w.y, layer: 0,
        draw: (g, sx, sy) => partition(g, sx, sy, w.axis) }));
      // кабинет преподавателя: стол, доска, шкаф, диван у коридора
      const fur = (kind: Parameters<typeof furniture>[1], x: number, y: number) =>
        items.push({ x, y, layer: 1, draw: (g, sx, sy) => furniture(g, kind, sx, sy, undefined, t) });
      fur("whiteboard", 2, 0); fur("plant", 1, 1); fur("shelf", 6, 1); fur("cooler", 6, plan.rows - 2);
      fur("sofa", 1, plan.rows - 2); fur("sofa", 2, plan.rows - 2);
      seated(items, "teacher", TEACHER.seat, TEACHER.desk, () => "sit", () => true, t);
      plan.cabins.forEach((cab, ci) => {
        fur("plant", cab.plant.x, cab.plant.y);
        const room = o.rooms[ci];
        if (!room?.lights) return;
        const { seats, desks } = roomLayout(room.agents.length, cab.rect);
        seats.forEach((seat, i) => {
          const a = room.agents[i];
          seated(items, a.key, seat, desks[i], (m) => (reduced ? "sit" : pose(a, m, i)), () => a.state === "typing", t);
        });
      });
      for (const it of depthOrder(items)) { const s = at(it.x, it.y); it.draw(ctx, s.x, s.y); }
      plan.cabins.forEach((cab, ci) => {
        const room = o.rooms[ci];
        if (!room?.lights) fillPoly(ctx, area(cab.rect), "rgba(11, 15, 20, 0.62)"); // свет выключен: ученик не в сети
        if (sel && room?.student?.id === sel) {
          ctx.strokeStyle = "#6366f1";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          area(cab.rect).forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
          ctx.closePath();
          ctx.stroke();
        }
      });
      view.imageSmoothingEnabled = false;
      view.clearRect(0, 0, W * scale, H * scale);
      view.drawImage(base, 0, 0, W * scale, H * scale);
    };
    const loop = (ms: number) => {
      if (ms - last >= RENDER_MS) { draw(ms); last = ms; }
      if (!reduced) raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [scale, reduced, plan, origin, W, H, reduced ? office : null, reduced ? selected : null]); // eslint-disable-line react-hooks/exhaustive-deps

  const px = (p: { x: number; y: number }) => ({ left: p.x * scale, top: p.y * scale });
  const pick = (e: React.MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const i = cabinAt(plan, toGrid((e.clientX - r.left) / scale, (e.clientY - r.top) / scale, origin));
    const student = i === null ? null : office.rooms[i]?.student;
    if (student) onRoom?.(student.id);
  };
  const label = "rounded bg-amber-50/95 px-1.5 text-xs font-medium text-amber-950 shadow whitespace-nowrap";
  return (
    <div ref={wrap} className="w-full overflow-x-auto">
      <div className={`relative ${onRoom ? "cursor-pointer" : ""}`} style={{ width: W * scale, height: H * scale }}
        onClick={pick}>
        <canvas ref={canvas} width={W * scale} height={H * scale} className="block rounded"
          style={{ imageRendering: "pixelated" }} role="img" aria-label="Офис: кабинет преподавателя и кабинеты учеников" />
        <div className={`absolute -translate-x-1/2 -translate-y-full ${label}`} style={px(toScreen(4, 1, origin))}>
          Преподаватель</div>
        {plan.cabins.map((cab, ci) => {
          const room = office.rooms[ci];
          if (!room) return null;
          // табличка — у двери, со стороны коридора
          const dark = isDark(room), p = toScreen(cab.rect.x0 + (cab.back ? 1.5 : 6), cab.door.y, origin);
          const pos = `absolute -translate-x-1/2 ${cab.back ? "translate-y-0.5" : "-translate-y-[calc(100%+2px)]"}`;
          const text = `${room.student ? room.student.name : "свободно"}${room.student && dark ? " · не в сети" : ""}`;
          return (
            <div key={room.seat}>
              {room.student && onRoom
                ? <button type="button" className={`${pos} ${label} ${
                  selected === room.student.id ? "ring-2 ring-indigo-500" : ""}`} style={px(p)}
                  onClick={(e) => { e.stopPropagation(); onRoom(room.student!.id); }}>{text}</button>
                : <div className={`${pos} ${label}`} style={px(p)}>{text}</div>}
              {!dark && roomLayout(room.agents.length, cab.rect).seats.map((seat, i) => {
                const a = room.agents[i], c = charAt(toScreen(seat.x, seat.y, origin)), bubble = bubbleFor(a.state);
                return (
                  <div key={a.key}>
                    <button type="button" className="absolute rounded focus:outline focus:outline-2 focus:outline-indigo-500"
                      style={{ ...px(c), width: CHAR_W * scale, height: (CHAR_H - 6) * scale }}
                      title={`${a.name} — ${STATE_LABEL[a.state]}`} aria-label={`${room.student?.name}: ${a.name}, ${STATE_LABEL[a.state]}`}
                      onClick={(e) => { e.stopPropagation(); if (room.student) onAgent?.(room.student.id, a); }} />
                    {bubble && <span className="pointer-events-none absolute -translate-x-1/2 -translate-y-full whitespace-nowrap rounded bg-slate-800/85 px-1 text-[10px] leading-4 text-white"
                      style={px({ x: c.x + CHAR_W / 2, y: c.y })}>{a.name} {bubble}</span>}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
