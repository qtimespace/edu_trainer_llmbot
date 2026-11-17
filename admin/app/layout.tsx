// стили React Flow (схема флоу) — в общем CSS: отдельным чанком Next предзагружал их на каждой странице впустую
import "@xyflow/react/dist/style.css";
import "./globals.css";
import type { ReactNode } from "react";

export const metadata = { title: "Учебный центр", description: "Тренажёр юного разработчика" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen text-sm antialiased">{children}</body>
    </html>
  );
}
