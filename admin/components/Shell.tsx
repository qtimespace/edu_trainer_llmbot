"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { menuFor } from "@/lib/nav";
import { usePresence } from "@/lib/presence";
import { useSession } from "@/lib/session";

export function Shell({ children }: { children: ReactNode }) {
  const { me, role, logout } = useSession();
  const path = usePathname();
  usePresence(role === "student"); // пока ученик здесь — в его комнате горит свет
  return (
    <div className="flex min-h-screen">
      <aside className="w-52 shrink-0 border-r border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mb-4 px-2 text-base font-semibold">Учебный центр</div>
        <nav aria-label="Меню">
          {menuFor(role).map((i) => (
            <Link key={i.href} href={i.href} className={`block rounded px-2 py-1 ${path.startsWith(i.href)
              ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
              : "hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}>{i.label}</Link>
          ))}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="flex items-center justify-end gap-3 border-b border-zinc-200 px-6 py-2 dark:border-zinc-800">
          <span className="text-zinc-500">{me.account.name || me.account.login}
            {role === "teacher" ? " · преподаватель" : ""}</span>
          <button className="text-zinc-500 hover:underline" onClick={logout}>Выйти</button>
        </header>
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}
