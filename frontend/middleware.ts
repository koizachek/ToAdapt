import { NextRequest, NextResponse } from 'next/server'
import { verifyTeacherSessionPayload, TEACHER_COOKIE } from '@/lib/teacherAuth'
import { PILOT_TUTOR_ONLY } from '@/lib/pilot'

const STUDENT_PATHS = ['/cases', '/results', '/goodbye']
const HIDDEN_TEACHER_PATHS = ['/admin', '/dashboard']

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname

  // Pilotphase: Studierenden-Ansichten → Login; Case-Generator/Individual-
  // Dashboard → Briefings. Nichts davon ist gelöscht, nur nicht erreichbar.
  const isStudentPath = STUDENT_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'))
  if (PILOT_TUTOR_ONLY) {
    if (isStudentPath) {
      return NextResponse.redirect(new URL('/?mode=teacher', request.url))
    }
    if (HIDDEN_TEACHER_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'))) {
      return NextResponse.redirect(new URL('/briefings', request.url))
    }
  } else if (isStudentPath) {
    // Ausserhalb der Pilotphase bleiben Studierenden-Seiten ohne Tutor-Session erreichbar.
    return NextResponse.next()
  }

  const token = request.cookies.get(TEACHER_COOKIE)?.value
  const session = await verifyTeacherSessionPayload(token)

  if (!session) {
    const redirectUrl = new URL('/?mode=teacher', request.url)
    const language = request.nextUrl.searchParams.get('language') ?? request.nextUrl.searchParams.get('lang')
    if (language === 'en') {
      redirectUrl.searchParams.set('language', 'en')
    }
    return NextResponse.redirect(redirectUrl)
  }

  // Alte Upload-Adresse → Briefings (Upload ist dort für den Master integriert).
  if (request.nextUrl.pathname.startsWith('/upload')) {
    return NextResponse.redirect(new URL('/briefings', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/admin/:path*', '/dashboard/:path*', '/guide/:path*', '/briefings/:path*', '/upload/:path*',
    '/cases/:path*', '/results/:path*', '/goodbye/:path*',
  ],
}
