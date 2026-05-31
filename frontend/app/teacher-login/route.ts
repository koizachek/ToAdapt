import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const code = String(formData.get('teacher_code') ?? '').trim()
  const teacherAccessCode = process.env.TEACHER_ACCESS_CODE ?? ['0', '0', '0', '0'].join('')

  if (code !== teacherAccessCode) {
    return NextResponse.redirect(new URL('/?mode=teacher&teacher_error=1', request.url), 303)
  }

  const response = NextResponse.redirect(new URL('/cases', request.url), 303)
  const secure = process.env.NODE_ENV === 'production'

  response.cookies.set('teacher_access', 'true', {
    httpOnly: true,
    sameSite: 'lax',
    secure,
    path: '/',
  })
  response.cookies.set('teacher_mode', 'true', {
    sameSite: 'lax',
    secure,
    path: '/',
  })

  return response
}
