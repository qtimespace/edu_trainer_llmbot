"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { Button, ErrorBox, Field, Input } from "@/components/ui";
import { api, setCsrf } from "@/lib/api";
import { homeFor } from "@/lib/nav";
import { safeNext } from "@/lib/redirect";
import type { AuthMe } from "@/lib/session";

function LoginForm() {
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const me = await api<AuthMe>("/auth/login", { method: "POST", body: { login, password } });
      setCsrf(me.csrf);
      const target = safeNext(next, window.location.origin);
      router.replace(target === "/" ? homeFor(me.account.role) : target);
    } catch (err) {
      setError(err as Error);
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="w-80 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800
      dark:bg-zinc-900">
      <h1 className="mb-4 text-lg font-semibold">Вход в учебный центр</h1>
      <ErrorBox error={error} />
      <Field label="Логин"><Input autoFocus autoComplete="username" value={login}
        onChange={(e) => setLogin(e.target.value)} /></Field>
      <Field label="Пароль"><Input type="password" autoComplete="current-password" value={password}
        onChange={(e) => setPassword(e.target.value)} /></Field>
      <Button type="submit" disabled={busy || !login || !password} className="w-full">Войти</Button>
    </form>
  );
}

export default function LoginPage() {
  return <div className="flex min-h-screen items-center justify-center"><Suspense><LoginForm /></Suspense></div>;
}
