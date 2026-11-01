// Клиент API тренажёра: все запросы идут через прокси Next (`/api/* → TRAINER_API_URL`), одно происхождение с cookie.
const UNAVAILABLE = "Сервис недоступен, повторите позже";

type PydanticError = { loc?: unknown[]; msg?: string };

export function errorText(status: number, detail: unknown): string {
  // 5xx без причины — прокси или сеть; с причиной в detail — ответ самого API, его и показываем
  if (status === 0 || ((status === 502 || status === 503 || status === 504) && !(typeof detail === "string" && detail))) {
    return UNAVAILABLE;
  }
  if (status === 428 && detail && typeof detail === "object" && "missing" in detail) {
    return `Не хватает доступов: ${(detail as { missing: string[] }).missing.join(", ")} — откройте «Мои доступы»`;
  }
  if (Array.isArray(detail)) {
    return detail.map((d: string | PydanticError) => (typeof d === "string" ? d
      : `${(d.loc ?? []).filter((x) => x !== "body").join(".")}: ${d.msg ?? ""}`)).join("; ");
  }
  if (typeof detail === "string" && detail) return detail;
  if (status === 500) return "Сервис недоступен или внутренняя ошибка — повторите позже"; // так отвечает и прокси Next
  if (status === 403) return "Нет прав на это действие";
  if (status === 404) return "Не найдено";
  return `Ошибка ${status}`;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(errorText(status, detail));
  }
}

let csrf = "";
export function setCsrf(value: string) { csrf = value; }

type Events = { unauthorized?: () => void; notReady?: () => void };
let events: Events = {};
export function onApiEvents(handlers: Events) { events = handlers; }

type Options = { method?: "GET" | "POST" | "PUT" | "DELETE"; body?: unknown; text?: boolean };

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = csrf;
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method, headers, credentials: "same-origin",
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body) });
  } catch {
    throw new ApiError(0, null);
  }
  if (res.status === 401 && !path.startsWith("/auth/login")) events.unauthorized?.();
  if (res.status === 428) events.notReady?.();
  if (!res.ok) {
    let detail: unknown = null;
    try { detail = (await res.json()).detail; } catch { /* не JSON — прокси или сеть */ }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (opts.text ? await res.text() : await res.json()) as T;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const isUuid = (id: string) => UUID.test(id);
