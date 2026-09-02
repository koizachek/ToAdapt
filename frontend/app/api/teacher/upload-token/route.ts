import { NextRequest, NextResponse } from 'next/server'
import { verifyTeacherSessionPayload, TEACHER_COOKIE } from '@/lib/teacherAuth'

// Kurzlebiges Upload-Token für den Direkt-Upload Browser → Backend (Railway).
// Grund: Vercel begrenzt Request-Bodies von Route-Handlern auf 4,5 MB
// (Infrastruktur-Limit, nicht konfigurierbar) — ein Semester-ZIP mit
// hunderten PPTX-Abgaben passt nicht durch den Teacher-Proxy.
//
// Signatur identisch zu backend/briefings/upload_token.py: HMAC-SHA256 über
// die Base64url-Payload, Schlüssel = TOADAPT_API_KEY. Nur der Master-Tutor
// (signiertes Master-Flag in der Session) bekommt ein Token; es gilt nur für
// POST /briefings/upload und läuft nach TTL_SECONDS ab.

const TTL_SECONDS = 15 * 60

const BACKEND =
  process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function toBase64Url(bytes: Uint8Array): string {
  let binary = ''
  for (const b of bytes) binary += String.fromCharCode(b)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

async function hmacSha256(message: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(message))
  return toBase64Url(new Uint8Array(sig))
}

export async function POST(request: NextRequest) {
  const token = request.cookies.get(TEACHER_COOKIE)?.value
  const session = await verifyTeacherSessionPayload(token)
  if (!session) {
    return NextResponse.json({ detail: 'Nicht autorisiert' }, { status: 401 })
  }
  if (!session.master) {
    return NextResponse.json({ detail: 'Nur für den Master-Tutor' }, { status: 403 })
  }
  const apiKey = process.env.TOADAPT_API_KEY
  if (!apiKey) {
    return NextResponse.json({ detail: 'Backend-Auth nicht konfiguriert' }, { status: 503 })
  }

  const exp = Math.floor(Date.now() / 1000) + TTL_SECONDS
  const payload = JSON.stringify({
    exp,
    tutor: session.tutor,
    master: true,
    jti: session.jti ?? crypto.randomUUID(),
  })
  const body = toBase64Url(new TextEncoder().encode(payload))
  const sig = await hmacSha256(body, apiKey)

  // Die öffentliche Backend-URL für den Browser: NEXT_PUBLIC_API_URL ist die
  // vom Studierenden-Flow ohnehin genutzte, CORS-freigegebene Adresse.
  const uploadUrl = `${process.env.NEXT_PUBLIC_API_URL || BACKEND}/briefings/upload`
  return NextResponse.json({ token: `${body}.${sig}`, upload_url: uploadUrl, expires_at: exp })
}
