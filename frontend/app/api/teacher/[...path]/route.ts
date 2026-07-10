import { NextRequest, NextResponse } from 'next/server'
import { verifyTeacherSessionPayload, TEACHER_COOKIE } from '@/lib/teacherAuth'

// Server-seitiger Proxy für teacher-/dashboard-Backend-Calls.
// Der Browser spricht nur diesen Handler an (same-origin, cookie-authentifiziert);
// der geheime X-API-Key wird ausschließlich hier server-seitig ergänzt und
// gelangt nie ins Browser-Bundle.

const BACKEND =
  process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Diese Backend-Pfade sind dem Master-Tutor vorbehalten (signiertes
// Master-Flag in der Session) — reguläre Tutor:innen sehen die Ergebnisse
// nur aggregiert über /dashboard/groups.
const MASTER_ONLY_PREFIXES = ['group-uploads']

async function proxy(request: NextRequest, path: string[]): Promise<NextResponse> {
  const token = request.cookies.get(TEACHER_COOKIE)?.value
  const session = await verifyTeacherSessionPayload(token)
  if (!session) {
    return NextResponse.json({ detail: 'Nicht autorisiert' }, { status: 401 })
  }
  if (MASTER_ONLY_PREFIXES.includes(path[0] ?? '') && !session.master) {
    return NextResponse.json({ detail: 'Nur für den Master-Tutor' }, { status: 403 })
  }

  const apiKey = process.env.TOADAPT_API_KEY
  if (!apiKey) {
    return NextResponse.json({ detail: 'Backend-Auth nicht konfiguriert' }, { status: 503 })
  }

  const search = request.nextUrl.search
  const targetUrl = `${BACKEND}/${path.join('/')}${search}`

  // Content-Type des Originals durchreichen — bei Multipart-Uploads trägt
  // er die Boundary, ohne die das Backend den Body nicht parsen kann.
  const headers: Record<string, string> = {
    'X-API-Key': apiKey,
    'Content-Type': request.headers.get('content-type') ?? 'application/json',
  }

  const init: RequestInit = { method: request.method, headers }
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.arrayBuffer()
  }

  let upstream: Response
  try {
    upstream = await fetch(targetUrl, init)
  } catch {
    return NextResponse.json({ detail: 'Backend nicht erreichbar' }, { status: 502 })
  }

  const body = await upstream.text()
  return new NextResponse(body, {
    status: upstream.status,
    headers: { 'Content-Type': upstream.headers.get('Content-Type') ?? 'application/json' },
  })
}

type Ctx = { params: Promise<{ path: string[] }> }

export async function GET(request: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params
  return proxy(request, path)
}

export async function POST(request: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params
  return proxy(request, path)
}

export async function PATCH(request: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params
  return proxy(request, path)
}
