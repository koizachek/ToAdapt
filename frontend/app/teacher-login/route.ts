import { NextRequest, NextResponse } from 'next/server'
import { resolveTutorByCode, signTeacherSession, verifyArchiveCode, TEACHER_COOKIE, TEACHER_COOKIE_MAX_AGE } from '@/lib/teacherAuth'

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const code = String(formData.get('teacher_code') ?? '').trim()
  const language = String(formData.get('language') ?? '').trim()
  const languageParam = language === 'en' ? '&language=en' : ''

  // Master-Login: Der Master-Code (Env TEACHER_ARCHIVE_CODE, z.B. "000")
  // ist zugleich ein Login-Code — nur er schaltet die Master-Funktionen
  // frei (Upload der Gruppenarbeiten, Case-Archivierung).
  const isMaster = Boolean(code) && verifyArchiveCode(code)

  // Fail-closed: Einzelcodes (TEACHER_ACCESS_CODES) bzw. Legacy-Code —
  // ohne Treffer kein Zugang.
  const tutorId = code ? (resolveTutorByCode(code) ?? (isMaster ? 'master' : null)) : null
  if (!tutorId) {
    return NextResponse.redirect(new URL(`/?mode=teacher&teacher_error=1${languageParam}`, request.url), 303)
  }

  const response = NextResponse.redirect(new URL(`/cases${language === 'en' ? '?language=en' : ''}`, request.url), 303)
  const secure = process.env.NODE_ENV === 'production'

  // Signiertes, httpOnly Session-Cookie — nicht clientseitig fälschbar.
  const session = await signTeacherSession(tutorId, isMaster)
  response.cookies.set(TEACHER_COOKIE, session, {
    httpOnly: true,
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: TEACHER_COOKIE_MAX_AGE,
  })
  // UI-Hinweis-Cookies (nicht sicherheitsrelevant, steuern nur die Ansicht
  // bzw. füllen das Reviewer-Feld vor).
  response.cookies.set('teacher_mode', 'true', {
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: TEACHER_COOKIE_MAX_AGE,
  })
  response.cookies.set('teacher_name', encodeURIComponent(tutorId), {
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: TEACHER_COOKIE_MAX_AGE,
  })
  // UI-Hinweis (nicht sicherheitsrelevant): blendet den Upload-Reiter ein.
  // Durchgesetzt wird Master serverseitig (Middleware + Teacher-Proxy prüfen
  // das signierte Master-Flag).
  if (isMaster) {
    response.cookies.set('teacher_master', 'true', {
      sameSite: 'lax',
      secure,
      path: '/',
      maxAge: TEACHER_COOKIE_MAX_AGE,
    })
  } else {
    response.cookies.set('teacher_master', '', { path: '/', maxAge: 0 })
  }

  return response
}
