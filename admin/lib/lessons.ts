// Уроки и черновики заданий (экран преподавателя).
export type TaskStatus = "draft" | "todo" | "in_progress" | "waiting_student" | "done";
export type Check = { cmd: string; about: string };
export type TeacherTask = { id: string; lesson_id: string; student_id: string; agent_key: string; title: string;
  statement: string; status: TaskStatus; position: number; checks: Check[] };
export type Lesson = { id: string; title: string; description: string; position: number;
  prep_status: "idle" | "running" | "failed"; prep_error: string };

export function groupByStudent(tasks: TeacherTask[]): Map<string, TeacherTask[]> {
  const out = new Map<string, TeacherTask[]>();
  for (const t of tasks) out.set(t.student_id, [...(out.get(t.student_id) ?? []), t]);
  for (const list of out.values()) list.sort((a, b) => a.position - b.position);
  return out;
}

export const canApprove = (status: TaskStatus) => status === "draft";

export const STATUS_LABEL: Record<TaskStatus, string> = {
  draft: "черновик", todo: "к выполнению", in_progress: "в работе", waiting_student: "ждёт ученика", done: "готово",
};
