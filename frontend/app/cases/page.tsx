'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Nav from '@/components/Nav'
import { apiFetch } from '@/lib/api'
import { ArrowRight, BookOpen } from 'lucide-react'

interface CaseSummary {
  case_id: string
  title: string
  industry: string
  difficulty: string
  status: string
  created_at: string
}

const TP_LABEL: Record<string, string> = {
  tp1: 'TP 1 — Analyse',
  tp2: 'TP 2 — Strategie',
  tp3: 'TP 3 — Umsetzung',
  tp4: 'TP 4 — Integration',
  full: 'Vollständig',
}

export default function CasesPage() {
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!sessionStorage.getItem('app_mode')) {
      sessionStorage.setItem('app_mode', 'student')
    }
    apiFetch<CaseSummary[]>('/admin/cases?status=approved')
      .then(setCases)
      .catch(() => setCases([]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-14 flex items-end justify-between">
          <div>
            <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
              Case-Pool
            </p>
            <h1 className="font-display text-5xl leading-none" style={{ color: 'var(--ink)' }}>
              Cases
            </h1>
          </div>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            {cases.length} {cases.length === 1 ? 'Case' : 'Cases'} verfügbar
          </p>
        </div>

        <div className="divider mb-10" />

        {/* Case list */}
        {loading ? (
          <div className="flex items-center gap-3 py-20" style={{ color: 'var(--muted)' }}>
            <span className="text-sm">Wird geladen…</span>
          </div>
        ) : cases.length === 0 ? (
          <div className="py-20 text-center">
            <BookOpen size={32} style={{ color: 'var(--muted)' }} className="mx-auto mb-4" />
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              Noch keine Cases freigegeben.
            </p>
          </div>
        ) : (
          <ul className="flex flex-col">
            {cases.map((c, i) => (
              <li key={c.case_id}>
                {i > 0 && <div className="divider" />}
                <Link
                  href={`/cases/${c.case_id}`}
                  className="group flex items-center justify-between py-7 transition-all duration-150"
                >
                  <div className="flex items-start gap-8">
                    <span
                      className="text-xs font-mono mt-1 shrink-0"
                      style={{ color: 'var(--muted)', minWidth: '2rem' }}
                    >
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <div>
                      <h2 className="text-lg font-medium mb-1 group-hover:text-[var(--accent)] transition-colors duration-150">
                        {c.title}
                      </h2>
                      <div className="flex items-center gap-4">
                        <span className="text-xs" style={{ color: 'var(--muted)' }}>
                          {c.industry}
                        </span>
                        <span
                          className="text-xs px-2 py-0.5 font-medium"
                          style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                        >
                          {TP_LABEL[c.difficulty] ?? c.difficulty}
                        </span>
                      </div>
                    </div>
                  </div>
                  <ArrowRight
                    size={16}
                    className="shrink-0 transition-transform duration-200 group-hover:translate-x-1"
                    style={{ color: 'var(--muted)' }}
                  />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  )
}
