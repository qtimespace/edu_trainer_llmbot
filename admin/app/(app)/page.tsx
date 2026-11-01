"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { homeFor } from "@/lib/nav";
import { useSession } from "@/lib/session";

export default function Home() {
  const { role } = useSession();
  const router = useRouter();
  useEffect(() => { router.replace(homeFor(role)); }, [role, router]);
  return null;
}
