// Экран терминала ученика (GET /group/students/{id}/terminal): куски вывода и размеры окна, данные — base64.
export type ScreenChunk = { id: number; kind: "out" | "size"; data: string };
export type Screen = { chunks: ScreenChunk[]; last: number };

export function decodeChunk(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function parseSize(b64: string): { cols: number; rows: number } | null {
  const m = /^(\d+)x(\d+)$/.exec(new TextDecoder().decode(decodeChunk(b64)));
  if (!m) return null;
  const cols = Number(m[1]), rows = Number(m[2]);
  return cols > 0 && rows > 0 && cols <= 500 && rows <= 200 ? { cols, rows } : null;
}
