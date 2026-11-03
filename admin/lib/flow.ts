// Флоу заданий (GET/PUT /flow): этапы по порядку и переходы; первый «todo» и последний «done» постоянные.
export type FlowStage = { key: string; name: string; agent_key: string | null };
export type Flow = { stages: FlowStage[]; transitions: [string, string][] };

export const has = (f: Flow, from: string, to: string) => f.transitions.some(([a, b]) => a === from && b === to);

export function addStage(f: Flow): Flow {
  let n = 1;
  while (f.stages.some((s) => s.key === `stage-${n}`)) n++;
  const stages = [...f.stages];
  stages.splice(stages.length - 1, 0, { key: `stage-${n}`, name: "Новый этап", agent_key: null });
  return { ...f, stages };
}

export const removeStage = (f: Flow, key: string): Flow => ({ stages: f.stages.filter((s) => s.key !== key),
  transitions: f.transitions.filter(([a, b]) => a !== key && b !== key) });

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
