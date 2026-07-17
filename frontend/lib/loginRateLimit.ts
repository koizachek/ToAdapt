// In-Memory-Rate-Limiter für den Teacher-Login (Sliding Window pro IP).
//
// Gleiche bewusste Einschränkung wie backend/ratelimit.py: Das Limit gilt pro
// Serverless-Instanz/Prozess, nicht global — als Brute-Force-Bremse gegen
// Code-Raten reicht das, eine exakte globale Quote ist es nicht.

const WINDOW_MS = 60_000
const MAX_ATTEMPTS = 10
const MAX_TRACKED_KEYS = 10_000

const attempts = new Map<string, number[]>()

/** true = Limit erreicht, Versuch NICHT zählen lassen und abweisen. */
export function loginRateLimited(key: string): boolean {
  const now = Date.now()
  const recent = (attempts.get(key) ?? []).filter(t => now - t < WINDOW_MS)

  if (recent.length >= MAX_ATTEMPTS) {
    attempts.set(key, recent)
    return true
  }

  recent.push(now)
  attempts.set(key, recent)

  if (attempts.size > MAX_TRACKED_KEYS) {
    for (const [k, times] of attempts) {
      if (!times.length || now - times[times.length - 1] > WINDOW_MS) attempts.delete(k)
    }
  }
  return false
}

/** Nur für Tests. */
export function resetLoginRateLimit(): void {
  attempts.clear()
}
