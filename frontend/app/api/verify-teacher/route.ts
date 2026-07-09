import { NextRequest, NextResponse } from 'next/server'
import { verifyTeacherSession, resolveTutorByCode, TEACHER_COOKIE } from '@/lib/teacherAuth'

// Bestätigt das EIGENE Passwort einer eingeloggten Lehrkraft — z.B. als
// Sicherung vor versehentlichem, unwiderruflichem Archivieren eines Cases.
// Das Passwort ist der Zugangscode aus dem Login (bei Tutor:innen "000"),
// serverseitig gegen TEACHER_ACCESS_CODES bzw. TEACHER_ACCESS_CODE geprüft —
// nie hardcodiert, nie im Browser-Bundle.
export async function POST(request: NextRequest): Promise<NextResponse> {
  const token = request.cookies.get(TEACHER_COOKIE)?.value
  const sessionTutor = await verifyTeacherSession(token)
  if (!sessionTutor) {
    return NextResponse.json({ ok: false, detail: 'Nicht autorisiert' }, { status: 401 })
  }

  let password = ''
  try {
    const body = await request.json()
    password = String(body?.password ?? '').trim()
  } catch {
    return NextResponse.json({ ok: false, detail: 'Ungültige Anfrage' }, { status: 400 })
  }

  // Nur das eigene Passwort zählt: der eingegebene Code muss auf dieselbe
  // Tutor-Kennung auflösen wie die aktive Session.
  const resolved = password ? resolveTutorByCode(password) : null
  const ok = Boolean(resolved && resolved === sessionTutor)
  return NextResponse.json({ ok }, { status: ok ? 200 : 401 })
}
