import { NextRequest, NextResponse } from 'next/server'

export function middleware(request: NextRequest) {
  const hasTeacherAccess = request.cookies.get('teacher_access')?.value === 'true'

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
