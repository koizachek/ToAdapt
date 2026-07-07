import { NextRequest, NextResponse } from 'next/server'
import { verifyTeacherSession, TEACHER_COOKIE } from '@/lib/teacherAuth'

export async function middleware(request: NextRequest) {
  const token = request.cookies.get(TEACHER_COOKIE)?.value
  const hasTeacherAccess = await verifyTeacherSession(token)

  if (!hasTeacherAccess) {
    const redirectUrl = new URL('/?mode=teacher', request.url)
    const language = request.nextUrl.searchParams.get('language') ?? request.nextUrl.searchParams.get('lang')
    if (language === 'en') {
      redirectUrl.searchParams.set('language', 'en')
    }
    return NextResponse.redirect(redirectUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/admin/:path*', '/dashboard/:path*'],
}
