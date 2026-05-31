'use client'

import { useEffect, useState } from 'react'
import Nav from '@/components/Nav'
import { apiFetch } from '@/lib/api'
import { Users, TrendingUp } from 'lucide-react'

interface LearningObjectiveScore { tag: string; avg_pct: number; n: number }
interface Overview {
  total_students: number; total_submissions: number; avg_percentage: number
  avg_canvas_alignment_pct: number; avg_rubric_fit_pct: number
  exemplar_submissions_count: number
  needs_human_review_count: number
  technical_fallback_count: number
  by_tp: Record<number, number>; by_bloom: Record<number, number>
  top_objectives: LearningObjectiveScore[]
}
interface StudentRow {
  matrikelnummer: string; submissions_count: number; avg_percentage: number
  avg_canvas_alignment_pct: number
  avg_rubric_fit_pct: number
  exemplar_submissions_count: number
  needs_human_review_count: number
  technical_fallback_count: number
  latest_percentage: number | null
  latest_canvas_alignment_pct: number | null
  latest_rubric_fit_pct: number | null
  latest_target_tp: number | null
  latest_evaluated_at: string | null
  by_tp: Record<number, number>
}

const BLOOM: Record<number, string> = { 2: 'Verstehen', 3: 'Anwenden', 4: 'Analysieren', 5: 'Evaluieren', 6: 'Synthese' }
const OBJECTIVE_LABELS: Record<string, string> = {
  analyse: 'Analyse',
  evaluieren: 'Evaluieren',
  integration: 'Integration',
  kpi: 'KPI',
  reflexion: 'Reflexion',
  transfer: 'Transfer',
  'trade-off': 'Trade-off',
}

function objectiveLabel(tag: string) {
  return OBJECTIVE_LABELS[tag] ?? tag
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map(part => part.length <= 3 ? part.toUpperCase() : part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function MiniBar({ pct, label }: { pct: number; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs w-24 shrink-0" style={{ color: 'var(--muted)' }}>{label}</span>
      <div className="flex-1 h-1.5" style={{ background: 'rgba(53,40,30,0.1)' }}>
        <div className="h-full transition-all duration-700" style={{ width: `${pct}%`, background: 'var(--accent)' }} />
      </div>
      <span className="text-xs w-10 text-right font-medium">{pct.toFixed(0)}%</span>
    </div>
  )
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [students, setStudents] = useState<StudentRow[]>([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    sessionStorage.setItem('app_mode', 'teacher')
    apiFetch<Overview>('/dashboard/overview').then(setOverview)
    apiFetch<StudentRow[]>('/dashboard/students').then(setStudents)
  }, [])

  const filtered = students.filter(s => s.matrikelnummer.includes(search))

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-5xl mx-auto">
        <div className="mb-12">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
            Lerner-Dashboard
          </p>
          <h1 className="font-display text-5xl leading-none">Dashboard</h1>
        </div>

        <div className="divider mb-10" />

        {overview && (
          <>
            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-6 mb-12">
              {[
                { label: 'Studierende', value: overview.total_students, icon: <Users size={14} /> },
                { label: 'Submissions', value: overview.total_submissions, icon: <TrendingUp size={14} /> },
                { label: 'Ø Score', value: `${overview.avg_percentage.toFixed(0)}%`, icon: null },
                { label: 'Ø Canvas-Fit', value: `${overview.avg_canvas_alignment_pct.toFixed(0)}%`, icon: null },
                { label: 'Exemplars', value: overview.exemplar_submissions_count, icon: null },
                {
                  label: 'Review/Fallback',
                  value: `${overview.needs_human_review_count}/${overview.technical_fallback_count}`,
                  icon: null,
                },
              ].map(k => (
                <div
                  key={k.label}
                  className="h-32 p-6 flex flex-col justify-between"
                  style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.12)' }}
                >
                  <div className="min-h-9 flex items-start gap-2" style={{ color: 'var(--muted)' }}>
                    {k.icon}
                    <span className="text-xs tracking-widest uppercase leading-snug">{k.label}</span>
                  </div>
                  <p className="font-display text-4xl leading-none tabular-nums">{k.value}</p>
                </div>
              ))}
            </div>

            {/* Bloom + TP breakdown */}
            <div className="grid grid-cols-2 gap-10 mb-14">
              <div>
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>Nach Bloom-Stufe</p>
                <div className="flex flex-col gap-3">
                  {Object.entries(overview.by_bloom).map(([lvl, pct]) => (
                    <MiniBar key={lvl} pct={pct} label={BLOOM[Number(lvl)] ?? `Bloom ${lvl}`} />
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>Nach TP</p>
                <div className="flex flex-col gap-3">
                  {Object.entries(overview.by_tp).map(([tp, pct]) => (
                    <MiniBar key={tp} pct={pct} label={`TP ${tp}`} />
                  ))}
                </div>
              </div>
            </div>

            {/* Weakest learning objectives */}
            {overview.top_objectives.length > 0 && (
              <div className="mb-14 p-6" style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.12)' }}>
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>Schwächste Lernziele</p>
                <div className="flex flex-col gap-3">
                  {overview.top_objectives.map(o => (
                    <div key={o.tag} className="flex items-center justify-between">
                      <span className="text-sm">{objectiveLabel(o.tag)}</span>
                      <div className="flex items-center gap-4">
                        <span className="text-xs" style={{ color: 'var(--muted)' }}>n={o.n}</span>
                        <span className="text-sm font-medium" style={{ color: o.avg_pct < 50 ? '#c0392b' : 'var(--ink)' }}>
                          {o.avg_pct.toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Student table */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <p className="text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
              Studierende ({filtered.length})
            </p>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Matrikelnummer suchen…"
              className="px-3 py-1.5 text-sm bg-transparent outline-none"
              style={{ border: '1px solid rgba(53,40,30,0.2)', color: 'var(--ink)', width: '220px' }}
            />
          </div>

          <div className="divider mb-0" />
          <div className="grid text-xs font-medium tracking-wide uppercase py-3 px-2" style={{ color: 'var(--muted)', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr 1fr 1fr' }}>
            <span>Matrikelnummer</span>
            <span className="text-right">Submissions</span>
            <span className="text-right">Ø Score</span>
            <span className="text-right">Review</span>
            <span className="text-right">TP 1</span>
            <span className="text-right">TP 2</span>
            <span className="text-right">TP 3</span>
          </div>
          <div className="divider" />

          {filtered.length === 0 ? (
            <p className="py-10 text-sm text-center" style={{ color: 'var(--muted)' }}>Noch keine Daten.</p>
          ) : (
            filtered.map((s, i) => (
              <div key={s.matrikelnummer}>
                <div
                  className="grid items-center py-3 px-2 text-sm"
                  style={{ gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr 1fr 1fr' }}
                >
                  <span className="font-mono text-xs">{s.matrikelnummer}</span>
                  <span className="text-right" style={{ color: 'var(--muted)' }}>{s.submissions_count}</span>
                  <span className="text-right font-medium" style={{ color: s.avg_percentage >= 70 ? 'var(--accent)' : s.avg_percentage < 45 ? '#c0392b' : 'var(--ink)' }}>
                    {s.avg_percentage.toFixed(0)}%
                  </span>
                  <span className="text-right text-xs" style={{ color: s.needs_human_review_count > 0 ? '#c0392b' : 'var(--muted)' }}>
                    {s.needs_human_review_count}/{s.technical_fallback_count}
                  </span>
                  {[1, 2, 3].map(tp => (
                    <span key={tp} className="text-right text-xs" style={{ color: 'var(--muted)' }}>
                      {s.by_tp[tp] != null ? `${s.by_tp[tp].toFixed(0)}%` : '—'}
                    </span>
                  ))}
                </div>
                {i < filtered.length - 1 && <div className="divider" />}
              </div>
            ))
          )}
        </div>
      </main>
    </>
  )
}
