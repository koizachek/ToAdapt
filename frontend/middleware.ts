import { NextRequest, NextResponse } from 'next/server'

export function middleware(request: NextRequest) {
  const hasTeacherAccess = request.cookies.get('teacher_access')?.value === 'true'

  if (!hasTeacherAccess) {
    return NextResponse.redirect(new URL('/?mode=teacher', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/admin/:path*', '/dashboard/:path*'],
}
