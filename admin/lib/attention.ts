// Куда смотрит вкладка ученика (trainer/classroom/presence.py): текущее состояние, итоги за день, лента переходов.
export type AttentionState = "focused" | "blurred" | "hidden" | "offline";
export type Attention = { state: AttentionState; since: string | null };
export type AttentionLog = Attention & { totals: Record<"focused" | "blurred" | "hidden", number>;
  events: { state: AttentionState; at: string }[] };

export const ATTENTION: Record<AttentionState, { label: string; dot: string; text: string }> = {
  focused: { label: "смотрит", dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-400" },
  blurred: { label: "окно не в фокусе", dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-400" },
  hidden: { label: "вкладка скрыта", dot: "bg-red-500", text: "text-red-700 dark:text-red-400" },
  offline: { label: "не в сети", dot: "bg-zinc-400", text: "text-zinc-500" },
};

// состояние своей вкладки (у ученика): скрыта важнее фокуса — свёрнутый браузер может формально держать фокус
export function pageState(visibility: DocumentVisibilityState, focused: boolean): Exclude<AttentionState, "offline"> {
  if (visibility === "hidden") return "hidden";
  return focused ? "focused" : "blurred";
}

export function duration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  if (m < 1) return seconds > 0 ? "<1 мин" : "0 мин";
  const h = Math.floor(m / 60);
  return h ? `${h} ч ${m % 60} мин` : `${m} мин`;
}

export const ago = (since: string | null, now: number): string =>
  since ? duration(Math.max(0, Math.round((now - Date.parse(since)) / 1000))) : "";

// подпись на табличке кабинета в офисе
export function plateSuffix(online: boolean, attention: Attention | undefined, now: number): string {
  if (!online) return " · не в сети";
  if (!attention || attention.state === "offline") return "";
  if (attention.state === "focused") return " · смотрит";
  return ` · ${ATTENTION[attention.state].label} ${ago(attention.since, now)}`;
}

// доля времени «смотрит» среди всего времени в сети (для итога за день)
export function focusShare(totals: AttentionLog["totals"]): number | null {
  const all = totals.focused + totals.blurred + totals.hidden;
  return all ? Math.round((100 * totals.focused) / all) : null;
}
