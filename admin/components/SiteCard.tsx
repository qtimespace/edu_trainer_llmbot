"use client";
import { useEffect, useState } from "react";
import { Badge, Button, Card, ErrorBox, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { type SiteInfo, siteStatus } from "@/lib/site";

const STATUS = { on: ["green", "опубликован"], off: ["gray", "выключен"], nofolder: ["gray", "папка не задана"] } as const;

// Сайт ученика в интернете: папка в его доме, которую видно по адресу /s/<логин>/, и переключатель публикации.
export function SiteCard({ studentId }: { studentId: string }) {
  const site = useApi<SiteInfo>(`/group/students/${studentId}/site`);
  const [dir, setDir] = useState("");
  const [error, setError] = useState<Error | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => { if (site.data) setDir(site.data.site_dir ?? ""); }, [site.data]);
  if (!site.data) return null;
  const s = site.data;
  const save = (published: boolean) =>
    api<SiteInfo>(`/group/students/${studentId}/site`, { method: "PUT", body: { site_dir: dir.trim() || null, published } })
      .then(() => setError(null), setError).finally(site.reload);
  const [tone, label] = STATUS[siteStatus(s)];
  return (
    <Card title={<>Сайт <Badge tone={tone}>{label}</Badge></>} className="mb-4" actions={<>
      {s.published && <a href={s.url} target="_blank" rel="noreferrer" className="text-sm text-indigo-600 hover:underline">
        Открыть</a>}
      <Button variant="ghost" className="text-sm" onClick={() => navigator.clipboard.writeText(s.url)
        .then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); })}>
        {copied ? "Скопировано" : "Копировать адрес"}</Button>
    </>}>
      <ErrorBox error={error} />
      <p className="mb-2 text-sm text-zinc-600 dark:text-zinc-400">Адрес: <code>{s.url}</code> — открывается в любом
        браузере; ученик сохранил файл — на сайте сразу новая версия.</p>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm">Папка в /home/student/</span>
        <Input className="w-56" value={dir} onChange={(e) => setDir(e.target.value)}
          placeholder={s.suggested ?? "например site-maket"} />
        {s.suggested && s.suggested !== dir &&
          <Button variant="secondary" className="text-sm" onClick={() => setDir(s.suggested ?? "")}>
            Взять {s.suggested}</Button>}
        {s.published
          ? <><Button variant="secondary" onClick={() => save(true)}>Сохранить</Button>
            <Button variant="danger" onClick={() => save(false)}>Снять с публикации</Button></>
          : <Button disabled={!dir.trim()} onClick={() => save(true)}>Опубликовать</Button>}
      </div>
    </Card>
  );
}
