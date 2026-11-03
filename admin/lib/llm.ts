// Каталог моделей: ключи провайдеров и добавление моделей из их списков.
export type Provider = "openrouter" | "hf" | "zai" | "kimi" | "anthropic";
export const PROVIDERS: Record<Provider, string> = { openrouter: "OpenRouter", hf: "Hugging Face", zai: "Z.ai (GLM)",
  kimi: "Kimi (Moonshot)", anthropic: "Anthropic (Claude)" };
export type Offer = { model: string; name: string; context_window: number | null;
  pricing: { input: number; output: number } | null };

// ключ каталога — «провайдер/имя» (одна косая черта; в имени латиница, цифры, . _ : -)
export const modelKey = (provider: Provider, model: string) =>
  `${provider}/${model.replace(/[^A-Za-z0-9._:-]+/g, "-")}`;

// Прямые провайдеры цену (а Z.ai и окно) не отдают — их вводит преподаватель (manual)
export type Manual = { input: number; output: number; context_window: number };

export function modelBody(provider: Provider, o: Offer, manual?: Manual) {
  const body = { provider, model: o.model, capabilities: ["reasoning"],
    context_window: o.context_window ?? manual?.context_window,
    pricing: o.pricing ?? (manual && { input: manual.input, output: manual.output }) };
  // Claude думает перед ответом; low — короткий ответ тьютора не упирается в лимит вывода
  return provider === "anthropic" ? { ...body, effort: "low" } : body;
}
