import { NextRequest, NextResponse } from 'next/server'
import { verifyTeacherSession, verifyArchiveCode, TEACHER_COOKIE } from '@/lib/teacherAuth'

// Bestätigt den Master-Archiv-Code als Sicherung vor versehentlichem,
// unwiderruflichem Archivieren eines Cases. Nur der Master-Tutor kennt den
// Code (Env TEACHER_ARCHIVE_CODE, z.B. "000") — reguläre Tutor:innen können
// damit NICHT archivieren. Der Code wird serverseitig geprüft, nie hardcodiert,
// nie im Browser-Bundle. Voraussetzung ist zusätzlich eine gültige Session.
export async function POST(request: NextRequest): Promise<NextResponse> {
  const token = request.cookies.get(TEACHER_COOKIE)?.value
  if (!(await verifyTeacherSession(token))) {
    return NextResponse.json({ ok: false, detail: 'Nicht autorisiert' }, { status: 401 })
  }

  let password = ''
  try {
    const body = await request.json()
    password = String(body?.password ?? '').trim()
  } catch {
    return NextResponse.json({ ok: false, detail: 'Ungültige Anfrage' }, { status: 400 })
  }

  const ok = Boolean(password) && verifyArchiveCode(password)
  return NextResponse.json({ ok }, { status: ok ? 200 : 401 })
}
