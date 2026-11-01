// Каталог моделей: ключи провайдеров (OpenRouter, Hugging Face) и добавление моделей из их списков.
export type Provider = "openrouter" | "hf";
export const PROVIDERS: Record<Provider, string> = { openrouter: "OpenRouter", hf: "Hugging Face" };
export type Offer = { model: string; name: string; context_window: number | null;
  pricing: { input: number; output: number } | null };

// ключ каталога — «провайдер/имя» (одна косая черта; в имени латиница, цифры, . _ : -)
export const modelKey = (provider: Provider, model: string) =>
  `${provider}/${model.replace(/[^A-Za-z0-9._:-]+/g, "-")}`;

export function modelBody(provider: Provider, o: Offer) {
  return { provider, model: o.model, capabilities: ["reasoning"], context_window: o.context_window,
    pricing: o.pricing };
}
