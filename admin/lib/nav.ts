// Меню панели по роли: ученику — только своя комната; преподавателю — офис, группа, уроки, настройки.
export type Role = "teacher" | "student";
export type NavItem = { href: string; label: string };

const TEACHER: NavItem[] = [
  { href: "/office", label: "Офис" },
  { href: "/group", label: "Группа" },
  { href: "/lessons", label: "Уроки" },
  { href: "/settings/llm", label: "Модели и ключи" },
  { href: "/settings/agents", label: "Агенты" },
];
const STUDENT: NavItem[] = [{ href: "/room", label: "Моя комната" }];

export const menuFor = (role: Role): NavItem[] => (role === "teacher" ? TEACHER : STUDENT);
export const homeFor = (role: Role): string => (role === "teacher" ? "/office" : "/room");
