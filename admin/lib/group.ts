// Группа: 2–5 мест, ученики по местам.
export type Student = { account_id: string; login: string; name: string; seat: number; note: string;
  budget_usd: number; lesson_password: string };
export type Group = { id: string; name: string; size: number };

export const sizeOptions = () => [2, 3, 4, 5];

export function seatsView<T extends { seat: number }>(size: number, students: T[]): { seat: number; student: T | null }[] {
  return Array.from({ length: size }, (_, i) => ({ seat: i + 1, student: students.find((s) => s.seat === i + 1) ?? null }));
}
