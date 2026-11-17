// Буфер обмена в терминале: xterm по умолчанию шлёт на Ctrl+V код ^V, а ученику нужно вставить текст
// (например, переведённый из транслита). Ctrl+C копирует, только если что-то выделено, — иначе это «прервать программу».
export type KeyLike = { type: string; key: string; code: string; ctrlKey: boolean; shiftKey: boolean; metaKey: boolean };

export function clipboardKey(e: KeyLike, hasSelection: boolean): "paste" | "copy" | null {
  if (e.type !== "keydown" || !(e.ctrlKey || e.metaKey)) return null;
  const k = e.code ? e.code : `Key${e.key.toUpperCase()}`; // code — физическая клавиша, не зависит от раскладки
  if (k === "KeyV") return "paste";
  if (k === "KeyC" && (hasSelection || e.shiftKey)) return "copy";
  return null;
}
