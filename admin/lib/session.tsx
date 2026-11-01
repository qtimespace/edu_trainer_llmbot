"use client";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, onApiEvents, setCsrf } from "./api";
import type { Role } from "./nav";

export type AuthMe = {
  account: { id: string; login: string; name: string; role: Role; must_change_password: boolean };
  csrf: string;
};

type Session = { me: AuthMe; role: Role; reload: () => Promise<void>; logout: () => Promise<void> };

const Ctx = createContext<Session | null>(null);

export function useSession(): Session {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession вне SessionProvider");
  return s;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const pathRef = useRef(path);
  pathRef.current = path;
  const [me, setMe] = useState<AuthMe | null>(null);

  // При истёкшей сессии — на вход с возвратом на текущую страницу.
  const toLogin = useCallback(() => {
    router.replace(`/login?next=${encodeURIComponent(pathRef.current)}`);
  }, [router]);

  const reload = useCallback(async () => {
    const m = await api<AuthMe>("/auth/me");
    setCsrf(m.csrf);
    setMe(m);
  }, []);

  useEffect(() => {
    onApiEvents({ unauthorized: toLogin });
    reload().catch(toLogin);
  }, [reload, toLogin]);

  if (!me) return <div className="p-8 text-zinc-500">Загрузка…</div>;
  const session: Session = {
    me, role: me.account.role, reload,
    logout: async () => {
      await api("/auth/logout", { method: "POST" });
      router.replace("/login");
    },
  };
  return <Ctx.Provider value={session}>{children}</Ctx.Provider>;
}
