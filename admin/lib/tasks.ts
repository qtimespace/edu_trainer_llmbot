// Рабочее место ученика: задания, переписка с агентом, адрес терминала.
import type { TaskStatus } from "./lessons";

export type StudentTask = { id: string; lesson_id: string; agent_key: string; title: string; statement: string;
  status: TaskStatus; position: number };
export type ChatMessage = { id: string; author: "student" | "agent" | "system"; agent_key: string | null; text: string;
  created_at: string; checks: { about: string; passed: boolean }[] };
export type Chat = { status: TaskStatus; running: boolean; messages: ChatMessage[] };

const LABEL: Record<TaskStatus, string> = {
  draft: "черновик", todo: "к выполнению", in_progress: "в работе", waiting_student: "ждёт тебя", done: "готово",
};
export const statusLabel = (s: TaskStatus) => LABEL[s];

export const canStart = (s: TaskStatus) => s === "todo";
export const canSend = (s: TaskStatus, running: boolean) => !running && (s === "waiting_student" || s === "in_progress");

// В проде Caddy ведёт /ws/* прямо в API (Next не проксирует WebSocket); в разработке — NEXT_PUBLIC_WS_URL
export function wsUrl(loc: { protocol: string; host: string }, env: string | undefined): string {
  if (env) return `${env.replace(/\/$/, "")}/ws/terminal`;
  return `${loc.protocol === "https:" ? "wss:" : "ws:"}//${loc.host}/ws/terminal`;
}
