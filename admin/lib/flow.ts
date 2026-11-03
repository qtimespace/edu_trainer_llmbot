// Флоу заданий (GET/PUT /flow): этапы по порядку и переходы; первый «todo» и последний «done» постоянные.
export type FlowStage = { key: string; name: string; agent_key: string | null };
export type Point = { x: number; y: number };
export type Flow = { stages: FlowStage[]; transitions: [string, string][]; layout?: Record<string, Point> };

export const has = (f: Flow, from: string, to: string) => f.transitions.some(([a, b]) => a === from && b === to);

export function addStage(f: Flow): Flow {
  let n = 1;
  while (f.stages.some((s) => s.key === `stage-${n}`)) n++;
  const stages = [...f.stages];
  stages.splice(stages.length - 1, 0, { key: `stage-${n}`, name: "Новый этап", agent_key: null });
  return { ...f, stages };
}

export function removeStage(f: Flow, key: string): Flow {
  const layout = { ...(f.layout ?? {}) };
  delete layout[key];
  return { stages: f.stages.filter((s) => s.key !== key), transitions: f.transitions.filter(([a, b]) => a !== key && b !== key),
    layout };
}

export function moveStage(f: Flow, key: string, dir: -1 | 1): Flow {
  const i = f.stages.findIndex((s) => s.key === key), j = i + dir;
  if (i <= 0 || i >= f.stages.length - 1 || j <= 0 || j >= f.stages.length - 1) return f;
  const stages = [...f.stages];
  [stages[i], stages[j]] = [stages[j], stages[i]];
  return { ...f, stages };
}

export const toggle = (f: Flow, from: string, to: string): Flow => ({ ...f,
  transitions: has(f, from, to) ? f.transitions.filter(([a, b]) => !(a === from && b === to)) : [...f.transitions, [from, to]] });

export const updateStage = (f: Flow, key: string, patch: Partial<FlowStage>): Flow =>
  ({ ...f, stages: f.stages.map((s) => (s.key === key ? { ...s, ...patch } : s)) });

// --- схема (components/FlowGraph.tsx): этапы — узлы, переходы — стрелки -------------------------------------------
export type EdgeKind = "handoff" | "return" | "close"; // вперёд, назад, в «Готово»
export type GraphNode = { id: string; label: string; agent: string | null; fixed: boolean; position: Point };
export type GraphEdge = { id: string; source: string; target: string; kind: EdgeKind };

const STEP_X = 230; // без сохранённых позиций — этапы в ряд слева направо

export function graph(f: Flow): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const order = f.stages.map((s) => s.key);
  const nodes = f.stages.map((s, i): GraphNode => ({ id: s.key, label: s.name, agent: s.agent_key,
    fixed: s.key === "todo" || s.key === "done", position: f.layout?.[s.key] ?? { x: i * STEP_X, y: 0 } }));
  const edges = f.transitions.map(([a, b]): GraphEdge => ({ id: `${a}->${b}`, source: a, target: b,
    kind: b === "done" ? "close" : order.indexOf(b) < order.indexOf(a) ? "return" : "handoff" }));
  return { nodes, edges };
}

export const moveNode = (f: Flow, key: string, p: Point): Flow =>
  ({ ...f, layout: { ...(f.layout ?? {}), [key]: { x: Math.round(p.x), y: Math.round(p.y) } } });

// новая стрелка на схеме: не в «К выполнению», не из «Готово», без повторов
export function connect(f: Flow, from: string, to: string): Flow {
  if (from === to || to === "todo" || from === "done" || has(f, from, to)) return f;
  return { ...f, transitions: [...f.transitions, [from, to]] };
}

export const removeTransition = (f: Flow, from: string, to: string): Flow =>
  ({ ...f, transitions: f.transitions.filter(([a, b]) => !(a === from && b === to)) });
