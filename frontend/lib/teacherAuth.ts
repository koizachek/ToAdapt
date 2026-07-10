// Signiertes Teacher-Session-Cookie (HMAC-SHA256 über Web Crypto,
// funktioniert in Edge-Middleware UND Node-Route-Handlern).
//
// Ersetzt das frühere statische `teacher_access=true`, das jeder im Browser
// selbst setzen konnte. Der Token enthält einen Zeitstempel und läuft ab.

const COOKIE_NAME = 'teacher_session'
const MAX_AGE_SECONDS = 12 * 60 * 60 // 12 Stunden

function toBase64Url(bytes: Uint8Array): string {
  let binary = ''
  for (const b of bytes) binary += String.fromCharCode(b)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function fromBase64Url(input: string): Uint8Array {
  const padded = input.replace(/-/g, '+').replace(/_/g, '/')
  const binary = atob(padded)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

async function hmac(payloadB64: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(payloadB64))
  return toBase64Url(new Uint8Array(sig))
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false
  let diff = 0
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i)
  return diff === 0
}

function getSecret(): string {
  const secret = process.env.TEACHER_SESSION_SECRET
  if (!secret) throw new Error('TEACHER_SESSION_SECRET nicht konfiguriert')
  return secret
}

export interface TeacherSessionPayload {
  tutor: string
  /** true nur für den Master-Tutor (Login mit dem Master-Code, Env TEACHER_ARCHIVE_CODE). */
  master: boolean
}

/** Erzeugt einen signierten Session-Token mit Tutor-Kennung, Master-Flag + Ablaufzeitstempel. */
export async function signTeacherSession(tutorId: string, master = false): Promise<string> {
  const payload = JSON.stringify({ iat: Date.now(), tutor: tutorId, master })
  const payloadB64 = toBase64Url(new TextEncoder().encode(payload))
  const sig = await hmac(payloadB64, getSecret())
  return `${payloadB64}.${sig}`
}

/**
 * Prüft Signatur und Ablauf; gibt bei Erfolg Tutor-Kennung + Master-Flag
 * zurück, sonst null. Ältere Tokens ohne Master-Feld gelten als
 * Nicht-Master (fail-closed für Master-Funktionen).
 */
export async function verifyTeacherSessionPayload(
  token: string | undefined,
): Promise<TeacherSessionPayload | null> {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length !== 2) return null
  const [payloadB64, sig] = parts

  let expected: string
  try {
    expected = await hmac(payloadB64, getSecret())
  } catch {
    return null
  }
  if (!timingSafeEqual(sig, expected)) return null

  try {
    const payload = JSON.parse(new TextDecoder().decode(fromBase64Url(payloadB64)))
    const iat = Number(payload?.iat)
    if (!Number.isFinite(iat)) return null
    if (Date.now() - iat > MAX_AGE_SECONDS * 1000) return null
    const tutor = typeof payload?.tutor === 'string' && payload.tutor ? payload.tutor : 'teacher'
    return { tutor, master: payload?.master === true }
  } catch {
    return null
  }
}

/**
 * Prüft Signatur und Ablauf; gibt bei Erfolg die Tutor-Kennung zurück,
 * sonst null (truthiness-kompatibel zum früheren boolean).
 */
export async function verifyTeacherSession(token: string | undefined): Promise<string | null> {
  const payload = await verifyTeacherSessionPayload(token)
  return payload ? payload.tutor : null
}

/**
 * Löst einen eingegebenen Zugangscode zur Tutor-Kennung auf.
 *
 * TEACHER_ACCESS_CODES: JSON-Objekt {"kennung": "code", ...} — Einzelcodes
 * für alle Tutor:innen (Generator: scripts/generate_tutor_codes.py).
 * Fallback: TEACHER_ACCESS_CODE (Alt-Setup, Kennung "teacher").
 */
export function resolveTutorByCode(code: string): string | null {
  const raw = process.env.TEACHER_ACCESS_CODES
  if (raw) {
    let mapping: Record<string, string>
    try {
      mapping = JSON.parse(raw)
    } catch {
      return null
    }
    for (const [tutorId, tutorCode] of Object.entries(mapping)) {
      if (typeof tutorCode === 'string' && tutorCode.length > 0 && timingSafeEqual(code, tutorCode)) {
        return tutorId
      }
    }
    return null
  }

  const legacy = process.env.TEACHER_ACCESS_CODE
  if (legacy && timingSafeEqual(code, legacy)) return 'teacher'
  return null
}

/**
 * Prüft den Master-Archiv-Code gegen die Env `TEACHER_ARCHIVE_CODE`.
 *
 * Nur der Master-Tutor kennt diesen Code (z.B. "000") und darf damit Cases
 * archivieren — reguläre Tutor:innen mit ihren Login-Einzelcodes nicht. Der
 * Code ist NICHT hardcodiert, sondern liegt allein in der Env-Variable.
 * Fail-closed: ohne konfigurierten Code ist Archivieren gesperrt.
 */
export function verifyArchiveCode(code: string): boolean {
  const master = process.env.TEACHER_ARCHIVE_CODE
  if (!master) return false
  return timingSafeEqual(code, master)
}

export const TEACHER_COOKIE = COOKIE_NAME
export const TEACHER_COOKIE_MAX_AGE = MAX_AGE_SECONDS
