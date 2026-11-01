"use client";
import { useEffect, useRef } from "react";
import type { ChibiPose } from "@/lib/chibi";
import { depthOrder, type Facing, TH, toScreen, TW } from "@/lib/iso";
import { bubbleFor, isDark, type Room, ROOM_COLS, ROOM_ROWS, roomLayout, type RoomAgent, STATE_LABEL } from "@/lib/rooms";
import { BG, chairBack, chairSeat, CHAR_H, CHAR_W, desk, drawChibi, floorTile, furniture, monitor, slab, SLAB_H,
  WALL_H, wallBack, wallSide } from "./iso-sprites";

const PAD = 6;
const RENDER_MS = 150;
const FACING: Facing = "S";
type Item = { x: number; y: number; layer: number; draw: (g: CanvasRenderingContext2D, sx: number, sy: number) => void };

const ORIGIN = { ox: ROOM_ROWS * (TW / 2) + PAD, oy: WALL_H + PAD };
export const ROOM_W = (ROOM_COLS + ROOM_ROWS) * (TW / 2) + 2 * PAD;
export const ROOM_H = (ROOM_COLS + ROOM_ROWS) * (TH / 2) + WALL_H + SLAB_H + 2 * PAD;
// клетка → левый верх спрайта сидящего персонажа
const charAt = (s: { x: number; y: number }) => ({ x: s.x - CHAR_W / 2, y: s.y + TH / 2 - 23 });

function pose(a: RoomAgent, ms: number, i: number): ChibiPose {
  if (a.state !== "typing") return "sit";
  return Math.floor((ms + i * 130) / 250) % 2 ? "type1" : "type2";
}

export function RoomCanvas({ room, scale, reduced, onAgent }: { room: Room; scale: number; reduced: boolean;
  onAgent?: (a: RoomAgent) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const live = useRef(room);
  live.current = room;
  const dark = isDark(room);
  const layout = roomLayout(room.agents.length);

  useEffect(() => {
    const view = canvas.current?.getContext("2d");
    if (!view) return;
    const base = document.createElement("canvas");
    base.width = ROOM_W; base.height = ROOM_H;
    const ctx = base.getContext("2d");
    if (!ctx) return;
    const at = (x: number, y: number) => toScreen(x, y, ORIGIN);
    let raf = 0, last = -RENDER_MS;

    const draw = (ms: number) => {
      const r = live.current;
      const agents = r.lights ? r.agents : [];
      const { seats, desks } = roomLayout(agents.length);
      ctx.fillStyle = BG;
      ctx.fillRect(0, 0, ROOM_W, ROOM_H);
      for (let y = 1; y < ROOM_ROWS; y++) for (let x = 1; x < ROOM_COLS; x++) {
        const s = at(x, y);
        floorTile(ctx, s.x, s.y, (x + y) % 2 ? "wood" : "wood2");
      }
      for (let x = 1; x < ROOM_COLS; x++) { const s = at(x, ROOM_ROWS - 1); slab(ctx, s.x, s.y, "y"); }
      for (let y = 1; y < ROOM_ROWS; y++) { const s = at(ROOM_COLS - 1, y); slab(ctx, s.x, s.y, "x"); }
      for (let x = 0; x < ROOM_COLS; x++) { const s = at(x, 0); wallBack(ctx, s.x, s.y, x); }
      for (let y = 1; y < ROOM_ROWS; y++) { const s = at(0, y); wallSide(ctx, s.x, s.y, y); }
      const items: Item[] = [{ x: ROOM_COLS - 2, y: 1, layer: 1,
        draw: (g, sx, sy) => furniture(g, "plant", sx, sy, undefined, reduced ? 0 : ms) }];
      agents.forEach((a, i) => {
        const seat = seats[i], d = desks[i];
        items.push({ x: seat.x, y: seat.y, layer: 1, draw: (g, sx, sy) => chairSeat(g, sx, sy) });
        items.push({ x: seat.x, y: seat.y, layer: 2, draw: (g, sx, sy) => {
          const p = charAt({ x: sx, y: sy });
          drawChibi(g, a.key, reduced ? "sit" : pose(a, ms, i), "front", p.x, p.y, false);
        } });
        items.push({ x: seat.x, y: seat.y, layer: 0, draw: (g, sx, sy) => chairBack(g, sx, sy, FACING) });
        items.push({ x: d.x, y: d.y, layer: 1, draw: (g, sx, sy) => {
          desk(g, sx, sy);
          monitor(g, sx, sy, FACING, a.state === "typing", reduced ? 0 : ms);
        } });
      });
      for (const it of depthOrder(items)) { const s = at(it.x, it.y); it.draw(ctx, s.x, s.y); }
      if (!r.lights) { // свет выключен: ученик не в сети
        ctx.fillStyle = "rgba(11, 15, 20, 0.72)";
        ctx.fillRect(0, 0, ROOM_W, ROOM_H);
      }
      view.imageSmoothingEnabled = false;
      view.clearRect(0, 0, ROOM_W * scale, ROOM_H * scale);
      view.drawImage(base, 0, 0, ROOM_W * scale, ROOM_H * scale);
    };
    const loop = (ms: number) => {
      if (ms - last >= RENDER_MS) { draw(ms); last = ms; }
      if (!reduced) raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [scale, reduced, reduced ? room : null]); // eslint-disable-line react-hooks/exhaustive-deps

  const px = (p: { x: number; y: number }) => ({ left: p.x * scale, top: p.y * scale });
  return (
    <div className="relative" style={{ width: ROOM_W * scale, height: ROOM_H * scale }}>
      <canvas ref={canvas} width={ROOM_W * scale} height={ROOM_H * scale} className="block rounded"
        style={{ imageRendering: "pixelated" }} role="img"
        aria-label={room.student ? `Комната ${room.student.name}${dark ? ", свет выключен" : ""}` : "Свободное место"} />
      <div className="absolute left-2 top-2 rounded bg-amber-50/95 px-1.5 text-xs font-medium text-amber-950 shadow">
        {room.student ? room.student.name : "свободно"}{room.student && dark ? " · не в сети" : ""}
      </div>
      {!dark && room.agents.slice(0, layout.seats.length).map((a, i) => {
        const p = charAt(toScreen(layout.seats[i].x, layout.seats[i].y, ORIGIN));
        const bubble = bubbleFor(a.state);
        return (
          <div key={a.key}>
            <button type="button" className="absolute rounded focus:outline focus:outline-2 focus:outline-indigo-500"
              style={{ ...px(p), width: CHAR_W * scale, height: (CHAR_H - 6) * scale }}
              title={`${a.name} — ${STATE_LABEL[a.state]}`} aria-label={`${a.name}: ${STATE_LABEL[a.state]}`}
              onClick={() => onAgent?.(a)} />
            <span className="pointer-events-none absolute -translate-x-1/2 -translate-y-full whitespace-nowrap rounded bg-slate-800/85 px-1 text-[10px] leading-4 text-white"
              style={px({ x: p.x + CHAR_W / 2, y: p.y })}>{a.name}{bubble ? ` ${bubble}` : ""}</span>
          </div>
        );
      })}
    </div>
  );
}
