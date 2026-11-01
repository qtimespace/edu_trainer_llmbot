import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, errorText, onApiEvents, setCsrf } from "./api";

function reply(status: number, body?: unknown) {
  return vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status }));
}

afterEach(() => { vi.unstubAllGlobals(); onApiEvents({}); setCsrf(""); });

describe("api", () => {
  it("sends CSRF only on changing requests and goes through /api", async () => {
    const fetch = reply(200, { ok: true });
    vi.stubGlobal("fetch", fetch);
    setCsrf("tok");
    await api("/me");
    await api("/teams", { method: "POST", body: { name: "x" } });
    const [getUrl, getInit] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    const [, postInit] = fetch.mock.calls[1] as unknown as [string, RequestInit];
    expect(getUrl).toBe("/api/me");
    expect((getInit.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
    expect((postInit.headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok");
  });

  it("calls the unauthorized handler on 401 and notReady on 428", async () => {
    const unauthorized = vi.fn(), notReady = vi.fn();
    onApiEvents({ unauthorized, notReady });
    vi.stubGlobal("fetch", reply(401, { detail: "войдите в DocOps" }));
    await expect(api("/me")).rejects.toBeInstanceOf(ApiError);
    vi.stubGlobal("fetch", reply(428, { detail: { missing: ["llm"] } }));
    await expect(api("/flow/evaluate", { method: "POST" })).rejects.toMatchObject({ status: 428 });
    expect(unauthorized).toHaveBeenCalledOnce();
    expect(notReady).toHaveBeenCalledOnce();
  });

  it("does not redirect on a failed login", async () => {
    const unauthorized = vi.fn();
    onApiEvents({ unauthorized });
    vi.stubGlobal("fetch", reply(401, { detail: "неверный логин или пароль" }));
    await expect(api("/auth/login", { method: "POST", body: {} })).rejects.toThrow("неверный логин или пароль");
    expect(unauthorized).not.toHaveBeenCalled();
  });

  it("turns error codes into readable text", () => {
    expect(errorText(0, null)).toBe("Сервис недоступен, повторите позже");
    expect(errorText(502, null)).toBe("Сервис недоступен, повторите позже");
    // ответ самого API с причиной — показываем причину, а не «недоступен»
    expect(errorText(503, "хранилище секретов не настроено")).toBe("хранилище секретов не настроено");
    expect(errorText(502, "провайдер не ответил")).toBe("провайдер не ответил");
    // прокси Next отвечает 500 без тела, когда API не запущен
    expect(errorText(500, null)).toBe("Сервис недоступен или внутренняя ошибка — повторите позже");
    expect(errorText(403, undefined)).toBe("Нет прав на это действие");
    expect(errorText(409, "это последний администратор")).toBe("это последний администратор");
    expect(errorText(422, [{ loc: ["body", "name"], msg: "Field required" }])).toBe("name: Field required");
    expect(errorText(422, ["пароль короче 12 символов"])).toBe("пароль короче 12 символов");
    expect(errorText(428, { missing: ["vcs", "llm"] })).toBe("Не хватает доступов: vcs, llm — откройте «Мои доступы»");
  });

  it("returns undefined for 204 and text when asked", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    expect(await api("/auth/logout", { method: "POST" })).toBeUndefined();
    vi.stubGlobal("fetch", vi.fn(async () => new Response("--- a\n+++ b", { status: 200 })));
    expect(await api<string>("/agents/x/export", { text: true })).toBe("--- a\n+++ b");
  });

  it("maps a network failure to status 0", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    await expect(api("/me")).rejects.toMatchObject({ status: 0, message: "Сервис недоступен, повторите позже" });
  });
});

describe("isUuid", () => {
  it("accepts only uuids as path segments", async () => {
    const { isUuid } = await import("./api");
    expect(isUuid("0b6c7c0e-1a2b-4c3d-8e9f-001122334455")).toBe(true);
    expect(isUuid("../../me/sandbox/reset?")).toBe(false);
    expect(isUuid("abc")).toBe(false);
  });
});
