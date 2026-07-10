import { NextRequest, NextResponse } from 'next/server'
import { verifyTeacherSessionPayload, TEACHER_COOKIE } from '@/lib/teacherAuth'

export async function middleware(request: NextRequest) {
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

  // /upload ist dem Master-Tutor vorbehalten (Login mit dem Master-Code);
  // reguläre Tutor:innen landen im Dashboard.
  if (request.nextUrl.pathname.startsWith('/upload') && !session.master) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/admin/:path*', '/dashboard/:path*', '/guide/:path*', '/upload/:path*'],
}
