// Куда вернуть после входа: только путь в этом же происхождении. Проверяется разобранный URL, а не префикс строки:
// браузер выбрасывает табы и переводы строк и читает «\» как «/», поэтому «/\t/evil.com» — это «//evil.com».
const CONTROL_OR_BACKSLASH = /[\u0000-\u001f\u007f\\]/;

export function safeNext(next: string | null, origin: string): string {
  if (!next || !next.startsWith("/") || CONTROL_OR_BACKSLASH.test(next)) return "/";
  try {
    const url = new URL(next, origin);
    if (url.origin !== origin) return "/";
    // «/.//evil.com» нормализуется в путь «//evil.com» — его браузер снова прочтёт как чужой хост
    const out = url.pathname + url.search + url.hash;
    return out.startsWith("//") ? "/" : out;
  } catch {
    return "/";
  }
}
