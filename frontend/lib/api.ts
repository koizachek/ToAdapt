const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}

// Für geschützte teacher-/dashboard-Endpunkte: geht über den same-origin
// Proxy (/api/teacher/*), der server-seitig den X-API-Key ergänzt. Der Key
// liegt nie im Browser. Cookies werden für die Session-Prüfung mitgesendet.
export async function teacherFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`/api/teacher${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}
