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

/** Erzeugt einen signierten Session-Token mit Ablaufzeitstempel. */
export async function signTeacherSession(): Promise<string> {
  const payload = JSON.stringify({ iat: Date.now() })
  const payloadB64 = toBase64Url(new TextEncoder().encode(payload))
  const sig = await hmac(payloadB64, getSecret())
  return `${payloadB64}.${sig}`
}

/** Prüft Signatur und Ablauf eines Session-Tokens. */
export async function verifyTeacherSession(token: string | undefined): Promise<boolean> {
  if (!token) return false
  const parts = token.split('.')
  if (parts.length !== 2) return false
  const [payloadB64, sig] = parts

  let expected: string
  try {
    expected = await hmac(payloadB64, getSecret())
  } catch {
    return false
  }
  if (!timingSafeEqual(sig, expected)) return false

  try {
    const payload = JSON.parse(new TextDecoder().decode(fromBase64Url(payloadB64)))
    const iat = Number(payload?.iat)
    if (!Number.isFinite(iat)) return false
    if (Date.now() - iat > MAX_AGE_SECONDS * 1000) return false
    return true
  } catch {
    return false
  }
}

export const TEACHER_COOKIE = COOKIE_NAME
export const TEACHER_COOKIE_MAX_AGE = MAX_AGE_SECONDS
