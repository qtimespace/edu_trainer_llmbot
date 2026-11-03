// Доска заданий: колонки — этапы флоу преподавателя (GET /me/board, /group/students/{id}/board).
export type BoardAgent = { key: string; name: string };
export type BoardStage = { key: string; name: string; agent: BoardAgent | null };
export type BoardTask = { id: string; number: number; title: string; lesson: string; stage: string; status: string;
  running: boolean; agent: BoardAgent };
export type Board = { stages: BoardStage[]; transitions: [string, string][]; tasks: BoardTask[] };

export const START = "todo", DONE = "done";

export function columns(b: Board): { stage: BoardStage; tasks: BoardTask[] }[] {
  return b.stages.map((stage) => ({ stage, tasks: b.tasks.filter((t) => t.stage === stage.key) }));
}

// куда можно перенести карточку: ученик — по переходам флоу; преподаватель — куда угодно, кроме «К выполнению»
export function targets(b: Board, from: string, teacher: boolean): string[] {
  if (teacher) return from === DONE ? [] : b.stages.map((s) => s.key).filter((k) => k !== START && k !== from);
  return b.transitions.filter(([a]) => a === from).map(([, to]) => to);
}

export function dot(t: BoardTask): { color: string; label: string } {
  if (t.running) return { color: "bg-sky-500 animate-pulse", label: "агент думает" };
  if (t.status === "done") return { color: "bg-emerald-500", label: "готово" };
  if (t.status === "waiting_student") return { color: "bg-orange-500", label: "ждёт тебя" };
  if (t.status === "in_progress") return { color: "bg-sky-500", label: "в работе" };
  return { color: "bg-zinc-400", label: "не начато" };
}

export const initials = (name: string): string =>
  name.trim().split(/[\s-]+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "—";
