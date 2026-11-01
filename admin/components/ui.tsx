"use client";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes,
  TextareaHTMLAttributes } from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

export function Button({ variant = "primary", className, ...p }: ButtonHTMLAttributes<HTMLButtonElement> &
  { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  const tone = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-500",
    secondary: "border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800",
    danger: "bg-red-600 text-white hover:bg-red-500",
    ghost: "hover:bg-zinc-100 dark:hover:bg-zinc-800",
  }[variant];
  return <button className={cx("rounded-md px-3 py-1.5 font-medium disabled:opacity-50", tone, className)} {...p} />;
}

export function Card({ title, actions, children, className }: { title?: ReactNode; actions?: ReactNode;
  children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900",
      className)}>
      {(title || actions) && <header className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2><div className="flex gap-2">{actions}</div></header>}
      {children}
    </section>
  );
}

const TONES = {
  gray: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  yellow: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  red: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  blue: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
};
export type Tone = keyof typeof TONES;

export function Badge({ tone = "gray", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cx("inline-block rounded px-1.5 py-0.5 text-xs font-medium", TONES[tone])}>{children}</span>;
}

export function Field({ label, hint, children, className }: { label: string; hint?: ReactNode; children: ReactNode;
  className?: string }) {
  return (
    <label className={cx("mb-3 block", className)}>
      <span className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-zinc-500">{hint}</span>}
    </label>
  );
}

const box = "w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-950";
export const Input = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={cx(box, p.className)} />;
export const Textarea = (p: TextareaHTMLAttributes<HTMLTextAreaElement>) =>
  <textarea {...p} className={cx(box, "font-mono text-xs", p.className)} />;
export const Select = (p: SelectHTMLAttributes<HTMLSelectElement>) => <select {...p} className={cx(box, p.className)} />;

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { key: T; label: ReactNode }[]; value: T;
  onChange: (k: T) => void }) {
  return (
    <div className="mb-4 flex gap-1 border-b border-zinc-200 dark:border-zinc-800" role="tablist">
      {tabs.map((t) => (
        <button key={t.key} role="tab" aria-selected={t.key === value} onClick={() => onChange(t.key)}
          className={cx("-mb-px border-b-2 px-3 py-2",
            t.key === value ? "border-indigo-600 font-medium" : "border-transparent text-zinc-500")}>{t.label}</button>
      ))}
    </div>
  );
}

export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void;
  children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div role="dialog" aria-label={title}
        className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-lg bg-white p-5 dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex justify-between"><h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} aria-label="Закрыть">✕</button></div>
        {children}
      </div>
    </div>
  );
}

export function ErrorBox({ error }: { error: Error | string | null | undefined }) {
  if (!error) return null;
  const text = typeof error === "string" ? error : error.message;
  return <div role="alert" className="mb-3 rounded-md bg-red-50 p-3 text-red-800 dark:bg-red-950 dark:text-red-200">
    {text}</div>;
}

export const Loading = () => <div className="p-4 text-zinc-500">Загрузка…</div>;
export const Empty = ({ children }: { children: ReactNode }) =>
  <div className="p-4 text-center text-zinc-500">{children}</div>;

// Строка формы: поля фиксированной ширины и кнопка, выровненные по нижнему краю полей
export function FormRow({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-end gap-3 [&>button]:mb-3 [&>button]:shrink-0">{children}</div>;
}

export function PageTitle({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return <div className="mb-4 flex items-center justify-between gap-2">
    <h1 className="text-xl font-semibold">{children}</h1><div className="flex gap-2">{actions}</div></div>;
}

export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead><tr className="border-b border-zinc-200 text-xs text-zinc-500 dark:border-zinc-800">
          {head.map((h, i) => <th key={i} className="px-2 py-2 font-medium">{h}</th>)}</tr></thead>
        <tbody className="[&>tr]:border-b [&>tr]:border-zinc-100 dark:[&>tr]:border-zinc-800 [&_td]:px-2 [&_td]:py-2">
          {children}</tbody>
      </table>
    </div>
  );
}
