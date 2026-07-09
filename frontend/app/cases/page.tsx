'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Nav from '@/components/Nav'
import NotionIcon from '@/components/NotionIcon'
import { apiFetch } from '@/lib/api'
import { ArrowRight, BookOpen } from 'lucide-react'
import { languageQuery, Locale } from '@/lib/i18n'
import { useLanguage } from '@/lib/useLanguage'

interface CaseSummary {
  case_id: string
  title: string
  industry: string
  difficulty: string
  status: string
  created_at: string
}

const TP_LABEL: Record<Locale, Record<string, string>> = {
  de: {
    tp1: 'TP 1 - Analyse',
    tp2: 'TP 2 - Strategie',
    tp3: 'TP 3 - Umsetzung',
    tp4: 'TP 4 - Integration',
    full: 'Vollständig',
  },
  en: {
    tp1: 'TP 1 - Analysis',
    tp2: 'TP 2 - Strategy',
    tp3: 'TP 3 - Implementation',
    tp4: 'TP 4 - Integration',
    full: 'Full case',
  },
}

const CASES_TEXT = {
  de: {
    pool: 'Case-Pool',
    title: 'Cases',
    availableOne: 'Case verfügbar',
    availableMany: 'Cases verfügbar',
    loading: 'Wird geladen...',
    empty: 'Noch keine Cases freigegeben.',
    emptyForTp: 'Für die aktuelle Phase sind noch keine Cases freigegeben.',
    currentTp: (tp: number) => `Aktuelle Phase: TP ${tp}`,
    showAll: 'Alle Phasen anzeigen',
    showCurrent: 'Nur aktuelle Phase',
  },
  en: {
    pool: 'Case pool',
    title: 'Cases',
    availableOne: 'case available',
    availableMany: 'cases available',
    loading: 'Loading...',
    empty: 'No cases have been released yet.',
    emptyForTp: 'No cases have been released for the current phase yet.',
    currentTp: (tp: number) => `Current phase: TP ${tp}`,
    showAll: 'Show all phases',
    showCurrent: 'Current phase only',
  },
}

export default function CasesPage() {
  const [language] = useLanguage()
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [currentTp, setCurrentTp] = useState(1)
  const [showAll, setShowAll] = useState(false)
  const text = CASES_TEXT[language]

  useEffect(() => {
    if (!sessionStorage.getItem('app_mode')) {
      sessionStorage.setItem('app_mode', 'student')
    }
    apiFetch<{ current_tp: number }>('/tp')
      .then(r => setCurrentTp(r.current_tp))
      .catch(() => { /* Fallback TP 1 */ })
    apiFetch<CaseSummary[]>(`/admin/cases?status=approved&${languageQuery(language)}`)
      .then(setCases)
      .catch(() => setCases([]))
      .finally(() => setLoading(false))
  }, [language])

  // Standard: nur Cases der aktuellen Phase (+ full-Cases); umschaltbar.
  const visibleCases = showAll
    ? cases
    : cases.filter(c => c.difficulty === `tp${currentTp}` || c.difficulty === 'full')

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-14 flex items-end justify-between">
          <div>
            <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
              {text.pool}
            </p>
            <h1 className="font-display text-5xl leading-none flex items-center gap-4" style={{ color: 'var(--ink)' }}>
              <NotionIcon name="cases" size={44} />
              {text.title}
            </h1>
          </div>
          <div className="text-right">
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              {visibleCases.length} {visibleCases.length === 1 ? text.availableOne : text.availableMany}
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--accent)' }}>
              {text.currentTp(currentTp)}
              <button
                type="button"
                onClick={() => setShowAll(v => !v)}
                className="ml-3 underline"
                style={{ color: 'var(--muted)' }}
              >
                {showAll ? text.showCurrent : text.showAll}
              </button>
            </p>
          </div>
        </div>

        <div className="divider mb-10" />

        {/* Case list */}
        {loading ? (
          <div className="flex items-center gap-3 py-20" style={{ color: 'var(--muted)' }}>
            <span className="text-sm">{text.loading}</span>
          </div>
        ) : visibleCases.length === 0 ? (
          <div className="py-20 text-center">
            <BookOpen size={32} style={{ color: 'var(--muted)' }} className="mx-auto mb-4" />
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              {cases.length === 0 ? text.empty : text.emptyForTp}
            </p>
          </div>
        ) : (
          <ul className="flex flex-col">
            {visibleCases.map((c, i) => (
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
                          {TP_LABEL[language][c.difficulty] ?? c.difficulty}
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
