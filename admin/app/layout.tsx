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
