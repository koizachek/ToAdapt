import { NextRequest, NextResponse } from 'next/server'
import { signTeacherSession, TEACHER_COOKIE, TEACHER_COOKIE_MAX_AGE } from '@/lib/teacherAuth'

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const code = String(formData.get('teacher_code') ?? '').trim()
  const language = String(formData.get('language') ?? '').trim()
  const languageParam = language === 'en' ? '&language=en' : ''
  const teacherAccessCode = process.env.TEACHER_ACCESS_CODE

  // Fail-closed: ohne konfigurierten Code kein Zugang (kein "0000"-Fallback).
  if (!teacherAccessCode || code !== teacherAccessCode) {
    return NextResponse.redirect(new URL(`/?mode=teacher&teacher_error=1${languageParam}`, request.url), 303)
  }

  const response = NextResponse.redirect(new URL(`/cases${language === 'en' ? '?language=en' : ''}`, request.url), 303)
  const secure = process.env.NODE_ENV === 'production'

  // Signiertes, httpOnly Session-Cookie — nicht clientseitig fälschbar.
  const session = await signTeacherSession()
  response.cookies.set(TEACHER_COOKIE, session, {
    httpOnly: true,
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: TEACHER_COOKIE_MAX_AGE,
  })
  // UI-Hinweis-Cookie (nicht sicherheitsrelevant, steuert nur die Ansicht).
  response.cookies.set('teacher_mode', 'true', {
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: TEACHER_COOKIE_MAX_AGE,
  })

  return response
}
