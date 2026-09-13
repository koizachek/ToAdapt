import { NextRequest, NextResponse } from 'next/server'
import { TEACHER_HOME } from '@/lib/pilot'
import { loginRateLimited } from '@/lib/loginRateLimit'
import {
  MASTER_TUTOR_ID,
  PENDING_COOKIE,
  PENDING_MAX_AGE,
  openPendingPassword,
  sealPendingPassword,
  signTeacherSession,
  verifyArchiveCode,
  TEACHER_COOKIE,
  TEACHER_COOKIE_MAX_AGE,
} from '@/lib/teacherAuth'

// Login der Übungsgruppenleiter und des Masters (Owner-Entscheidung 2026-09-13).
//
// Zwei Felder: Konto + Passwort.
// - Master: Master-Code (Env TEACHER_ARCHIVE_CODE) in BEIDEN Feldern.
// - Übungsgruppenleiter: Konto UEGL01–UEGL26, Passwort selbst gewählt. Die
//   Prüfung macht das Backend (POST /auth/tutor/login, server-seitig mit
//   X-API-Key). Beim ersten Login hat das Konto noch kein Passwort: Das eben
//   eingegebene Passwort GILT, es wird verschlüsselt zwischengespeichert
//   (httpOnly-Cookie, 10 min) und der Nutzer bestätigt es einmal
//   ("Passwort wiederholen"). Nach einem eingelösten Einmalcode (Passwort
//   vergessen) wird stattdessen ein komplett neues Passwort festgelegt.
//
// Aktionen (Formularfeld `action`):
//   login             Konto + Passwort
//   confirm_password  Passwort-Wiederholung (erster Login)
//   set_password      Konto + neues Passwort + Wiederholung (nach Einmalcode)
//   reset_request     Konto → markiert "Zurücksetzen angefragt" für den Master
//
// Fehlercodes in ?teacher_error=…: 1 (Passwort falsch), rate, unknown,
// short (zu kurz), mismatch (Wiederholung stimmt nicht), exists (Konto hat
// schon ein Passwort), expired (Bestätigung zu spät), backend (Backend nicht
// erreichbar/konfiguriert).

const BACKEND =
  process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const ACCOUNT_RE = /^UEGL\s*0*(\d{1,2})$/i

function normalizeAccount(raw: string): string {
  const match = ACCOUNT_RE.exec(raw.trim())
  if (!match) return ''
  const n = Number(match[1])
  if (n < 0 || n > 26) return ''   // UEGL00 = Testkonto
  return `UEGL${String(n).padStart(2, '0')}`
}

async function backend(path: string, body: Record<string, string>): Promise<{ status: number; json: Record<string, unknown> }> {
  const apiKey = process.env.TOADAPT_API_KEY
  if (!apiKey) return { status: 503, json: {} }
  try {
    const res = await fetch(`${BACKEND}${path}`, {
      method: 'POST',
      headers: { 'X-API-Key': apiKey, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(8000),
    })
    const json = (await res.json().catch(() => ({}))) as Record<string, unknown>
    return { status: res.status, json }
  } catch {
    return { status: 502, json: {} }
  }
}

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const action = String(formData.get('action') ?? 'login').trim()
  const accountRaw = String(formData.get('account') ?? '').trim()
  const password = String(formData.get('password') ?? '')
  const passwordRepeat = String(formData.get('password_repeat') ?? '')
  const language = String(formData.get('language') ?? '').trim()
  const languageParam = language === 'en' ? '&language=en' : ''

  const back = (params: string) =>
    NextResponse.redirect(new URL(`/?mode=teacher&${params}${languageParam}`, request.url), 303)

  // Brute-Force-Bremse gegen Passwort-Raten (10 Versuche/Minute pro IP).
  const clientIp = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 'unknown'
  if (loginRateLimited(clientIp)) {
    return back('teacher_error=rate')
  }

  // Master: Code in beiden Feldern (Env TEACHER_ARCHIVE_CODE, nie hardcodiert).
  if (action === 'login' && accountRaw && password && verifyArchiveCode(accountRaw) && verifyArchiveCode(password)) {
    return issueSession(request, MASTER_TUTOR_ID, true, language)
  }

  const account = normalizeAccount(accountRaw)
  if (!account) {
    return back('teacher_error=unknown')
  }

  if (action === 'reset_request') {
    const res = await backend('/auth/tutor/reset-request', { account })
    if (res.status >= 500) return back('teacher_error=backend')
    return back(`teacher_notice=reset_requested&account=${account}`)
  }

  if (action === 'confirm_password') {
    const pending = await openPendingPassword(request.cookies.get(PENDING_COOKIE)?.value)
    if (!pending || pending.account !== account) {
      // Zwischenspeicher abgelaufen → noch einmal anmelden
      return back('teacher_error=expired')
    }
    if (passwordRepeat !== pending.password) return back(`teacher_error=mismatch&confirm_password=${account}`)
    const res = await backend('/auth/tutor/set-password', { account, password: pending.password })
    if (res.status === 409) return back('teacher_error=exists')
    if (res.status === 422) return back(`teacher_error=short&set_password=${account}`)
    if (res.status !== 200) return back('teacher_error=backend')
    return issueSession(request, account, false, language)
  }

  if (action === 'set_password') {
    if (password.length < 6) return back(`teacher_error=short&set_password=${account}`)
    if (password !== passwordRepeat) return back(`teacher_error=mismatch&set_password=${account}`)
    const res = await backend('/auth/tutor/set-password', { account, password })
    if (res.status === 409) return back('teacher_error=exists')
    if (res.status === 422) return back(`teacher_error=short&set_password=${account}`)
    if (res.status !== 200) return back('teacher_error=backend')
    return issueSession(request, account, false, language)
  }

  // action === 'login'
  if (!password) return back('teacher_error=1')
  const res = await backend('/auth/tutor/login', { account, password })
  if (res.status === 200 && res.json.status === 'set_password') {
    if (res.json.reason === 'reset_code') {
      return back(`set_password=${account}`)
    }
    // Erster Login: eingegebenes Passwort gilt — nur noch bestätigen.
    if (password.length < 6) return back(`teacher_error=short&set_password=${account}`)
    const response = back(`confirm_password=${account}`)
    response.cookies.set(PENDING_COOKIE, await sealPendingPassword(account, password), {
      httpOnly: true,
      sameSite: 'lax',
      secure: process.env.NODE_ENV === 'production',
      path: '/',
      maxAge: PENDING_MAX_AGE,
    })
    return response
  }
  if (res.status === 200 && res.json.status === 'ok') {
    return issueSession(request, account, false, language)
  }
  if (res.status === 401) return back('teacher_error=1')
  if (res.status === 404) return back('teacher_error=unknown')
  if (res.status === 429) return back('teacher_error=rate')
  return back('teacher_error=backend')
}

async function issueSession(request: NextRequest, tutorId: string, isMaster: boolean, language: string) {
  const response = NextResponse.redirect(
    new URL(`${TEACHER_HOME}${language === 'en' ? '?language=en' : ''}`, request.url),
    303,
  )
  const secure = process.env.NODE_ENV === 'production'

  // Zwischenspeicher des ersten Logins ist damit erledigt.
  response.cookies.set(PENDING_COOKIE, '', { httpOnly: true, sameSite: 'lax', secure, path: '/', maxAge: 0 })
  // Signiertes, httpOnly Session-Cookie — nicht clientseitig fälschbar.
  const session = await signTeacherSession(tutorId, isMaster)
  response.cookies.set(TEACHER_COOKIE, session, {
    httpOnly: true,
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: TEACHER_COOKIE_MAX_AGE,
  })
  // UI-Hinweis-Cookies (nicht sicherheitsrelevant, steuern nur die Ansicht).
  response.cookies.set('teacher_mode', 'true', { sameSite: 'lax', secure, path: '/', maxAge: TEACHER_COOKIE_MAX_AGE })
  response.cookies.set('teacher_name', encodeURIComponent(tutorId), {
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: TEACHER_COOKIE_MAX_AGE,
  })
  // UI-Hinweis: blendet das Monitoring ein. Durchgesetzt wird Master
  // serverseitig (signiertes Flag → Header X-Teacher-Master im Proxy).
  if (isMaster) {
    response.cookies.set('teacher_master', 'true', { sameSite: 'lax', secure, path: '/', maxAge: TEACHER_COOKIE_MAX_AGE })
  } else {
    response.cookies.set('teacher_master', '', { path: '/', maxAge: 0 })
  }
  return response
}
