// Работа ученика глазами преподавателя (apps/api/review.py): переписка, команды в терминале, разбор задания.
export type ChatItem = { at: string; author: "student" | "agent" | "system"; agent: string | null; task_id: string;
  task_title: string; text: string; model: string | null; cost_usd: number | null; reason: string | null };
export type ConsoleItem = { at: number; where: "lobby" | "student"; cmd: string };
export type InspectCheck = { about: string; cmd: string; passed: boolean; output: string };
export type InspectFile = { path: string; note: string };
export type Inspect = { checks: InspectCheck[]; files: InspectFile[] };
export type Analysis = { text: string; model: string; cost_usd: number };

export const REVIEW_TABS = ["board", "chat", "console", "review"] as const;
export type ReviewTab = (typeof REVIEW_TABS)[number];
export const reviewTab = (v: string | null): ReviewTab =>
  (REVIEW_TABS as readonly string[]).includes(v ?? "") ? (v as ReviewTab) : "board";

// время команды из истории bash (unix-секунды; 0 — время не записано)
export const clock = (unix: number): string =>
  unix ? new Date(unix * 1000).toLocaleTimeString("ru", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";

export const prompt = (where: ConsoleItem["where"]): string => (where === "lobby" ? "lobby$" : "student@lab$");

// новый день в ленте команд — заголовок с датой
export function dayBreaks(items: ConsoleItem[]): Set<number> {
  const out = new Set<number>();
  let last = "";
  items.forEach((c, i) => {
    const day = c.at ? new Date(c.at * 1000).toDateString() : last;
    if (day !== last) out.add(i);
    last = day;
  });
  return out;
}

export const failedCount = (r: Inspect): number => r.checks.filter((c) => !c.passed).length;
