// Сайт ученика (GET/PUT /group/students/{id}/site): адрес /s/<логин>/, папку и публикацию задаёт преподаватель.
export type SiteInfo = { site_dir: string | null; published: boolean; suggested: string | null; url: string };

export function siteStatus(s: SiteInfo): "nofolder" | "off" | "on" {
  if (!s.site_dir) return "nofolder";
  return s.published ? "on" : "off";
}
