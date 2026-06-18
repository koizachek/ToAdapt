import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const code = String(formData.get('teacher_code') ?? '').trim()
  const language = String(formData.get('language') ?? '').trim()
  const languageParam = language === 'en' ? '&language=en' : ''
  const teacherAccessCode = process.env.TEACHER_ACCESS_CODE ?? ['0', '0', '0', '0'].join('')

  if (code !== teacherAccessCode) {
    return NextResponse.redirect(new URL(`/?mode=teacher&teacher_error=1${languageParam}`, request.url), 303)
  }

  const response = NextResponse.redirect(new URL(`/cases${language === 'en' ? '?language=en' : ''}`, request.url), 303)
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
