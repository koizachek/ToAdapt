import { NextRequest, NextResponse } from 'next/server'
import { TEACHER_COOKIE } from '@/lib/teacherAuth'

export async function POST(request: NextRequest) {
  const formData = await request.formData().catch(() => null)
  const language = String(formData?.get('language') ?? '').trim()
  const languageParam = language === 'en' ? '&language=en' : ''

  const response = NextResponse.redirect(new URL(`/?mode=teacher${languageParam}`, request.url), 303)
  const secure = process.env.NODE_ENV === 'production'

  // Die signierte Session ist httpOnly und damit clientseitig nicht löschbar —
  // ohne diesen Endpunkt bliebe sie nach einem "Abmelden" in der UI bis zu
  // 12 h gültig (relevant auf geteilten Tutorats-Laptops).
  response.cookies.set(TEACHER_COOKIE, '', {
    httpOnly: true,
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: 0,
  })
  // UI-Hinweis-Cookies (Ansichtssteuerung) ebenfalls entfernen.
  for (const name of ['teacher_mode', 'teacher_name', 'teacher_master']) {
    response.cookies.set(name, '', { sameSite: 'lax', secure, path: '/', maxAge: 0 })
  }

  return response
}
