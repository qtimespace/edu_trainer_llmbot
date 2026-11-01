const MAX_BACKOFF_MS = 60_000;

// Через сколько опросить снова: null — не опрашивать. Сбой опроса не останавливает его, а растягивает паузу.
export function nextPoll<T>({ pollMs, data, failures, until }: { pollMs?: number; data: T | null; failures: number;
  until?: (d: T) => boolean }): number | null {
  if (!pollMs) return null;
  if (failures > 0) return Math.min(pollMs * 2 ** failures, MAX_BACKOFF_MS);
  if (data === null || (until && until(data))) return null;
  return pollMs;
}
