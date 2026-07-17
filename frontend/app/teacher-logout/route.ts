import { NextRequest, NextResponse } from 'next/server'
import { TEACHER_COOKIE, verifyTeacherSessionPayload } from '@/lib/teacherAuth'

const BACKEND =
  process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  const formData = await request.formData().catch(() => null)
  const language = String(formData?.get('language') ?? '').trim()
  const languageParam = language === 'en' ? '&language=en' : ''

  // Session serverseitig widerrufen (Sperrliste im Backend): Damit ist auch
  // ein kopierter Token sofort ungültig, nicht erst nach dem 12-h-Ablauf.
  // Best-effort — das Cookie wird auch gelöscht, wenn das Backend nicht
  // erreichbar ist (der Token läuft dann regulär ab).
  const session = await verifyTeacherSessionPayload(request.cookies.get(TEACHER_COOKIE)?.value)
  const apiKey = process.env.TOADAPT_API_KEY
  if (session?.jti && apiKey) {
    try {
      await fetch(`${BACKEND}/auth/teacher-session/revoke`, {
        method: 'POST',
        headers: { 'X-API-Key': apiKey, 'Content-Type': 'application/json' },
        body: JSON.stringify({ jti: session.jti }),
        signal: AbortSignal.timeout(3000),
      })
    } catch {
      // bewusst geschluckt — Logout darf nie am Backend scheitern
    }
  }

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
