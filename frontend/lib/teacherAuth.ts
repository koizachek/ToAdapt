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
  /** true nur für den Master (Login mit dem Master-Code aus TEACHER_ARCHIVE_CODE in beiden Feldern). */
  master: boolean
  /** Session-ID für den serverseitigen Widerruf beim Logout; fehlt bei Alt-Tokens. */
  jti?: string
}

/** Erzeugt einen signierten Session-Token mit Tutor-Kennung, Master-Flag, Session-ID + Ablaufzeitstempel. */
export async function signTeacherSession(tutorId: string, master = false): Promise<string> {
  const payload = JSON.stringify({ iat: Date.now(), tutor: tutorId, master, jti: crypto.randomUUID() })
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
    const jti = typeof payload?.jti === 'string' && payload.jti ? payload.jti : undefined
    return { tutor, master: payload?.master === true, jti }
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
 * Prüft den Master-Code gegen die Env `TEACHER_ARCHIVE_CODE`.
 *
 * Der Master loggt sich mit diesem Code in BEIDEN Feldern (Konto und
 * Passwort) ein; nur er sieht das Monitoring und darf Cases archivieren. Die
 * Übungsgruppenleiter (Konten UEGL01–UEGL26) haben eigene, selbst gewählte
 * Passwörter, die das Backend prüft (POST /auth/tutor/login). Der Code ist
 * NICHT hardcodiert, sondern liegt allein in der Env-Variable.
 * Fail-closed: ohne konfigurierten Code gibt es keinen Master.
 */
export function verifyArchiveCode(code: string): boolean {
  const master = process.env.TEACHER_ARCHIVE_CODE
  if (!master) return false
  return timingSafeEqual(code, master)
}

export const TEACHER_COOKIE = COOKIE_NAME
export const TEACHER_COOKIE_MAX_AGE = MAX_AGE_SECONDS

export const MASTER_TUTOR_ID = 'master'

// ── Erster Login: Passwort bestätigen ─────────────────────────────────────
// Beim ersten Login gilt das eingegebene Passwort; der Nutzer bestätigt es
// danach einmal. Zwischen den beiden Requests liegt es AES-GCM-verschlüsselt
// in einem httpOnly-Cookie mit 10 Minuten Laufzeit (Schlüssel aus
// TEACHER_SESSION_SECRET). Nie im Klartext, nie in der URL.

export const PENDING_COOKIE = 'teacher_pending'
export const PENDING_MAX_AGE = 10 * 60

async function aesKey(): Promise<CryptoKey> {
  const raw = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(getSecret() + ':pending'))
  return crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt'])
}

export async function sealPendingPassword(account: string, password: string): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12)) as Uint8Array<ArrayBuffer>
  const payload = new TextEncoder().encode(JSON.stringify({ account, password, exp: Date.now() + PENDING_MAX_AGE * 1000 }))
  const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, await aesKey(), payload))
  return `${toBase64Url(iv)}.${toBase64Url(cipher)}`
}

export async function openPendingPassword(token: string | undefined): Promise<{ account: string; password: string } | null> {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length !== 2) return null
  try {
    const iv = fromBase64Url(parts[0]) as Uint8Array<ArrayBuffer>
    const cipher = fromBase64Url(parts[1]) as Uint8Array<ArrayBuffer>
    const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, await aesKey(), cipher)
    const data = JSON.parse(new TextDecoder().decode(plain))
    if (typeof data?.account !== 'string' || typeof data?.password !== 'string') return null
    if (Number(data?.exp) < Date.now()) return null
    return { account: data.account, password: data.password }
  } catch {
    return null
  }
}
