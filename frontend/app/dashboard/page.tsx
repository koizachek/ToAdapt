'use client'

import { useEffect, useState } from 'react'
import Nav from '@/components/Nav'
import { teacherFetch } from '@/lib/api'
import { APP_MODE_STORAGE_KEY } from '@/lib/appMode'
import { Locale } from '@/lib/i18n'
import { useLanguage } from '@/lib/useLanguage'
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
interface PenaltyCount { text: string; count: number }
interface ObjectiveDifficulty { tag: string; avg_pct: number; n: number }
interface CohortObjective { tag: string; avg_pct: number; students_below: number; students_total: number }
interface StudentDifficulty {
  matrikelnummer: string
  attention_level: 'high' | 'medium' | 'low'
  attention_reasons: string[]
  submissions_count: number
  avg_percentage: number
  latest_percentage: number | null
  latest_target_tp: number | null
  weak_objectives: ObjectiveDifficulty[]
  weak_blooms: Record<number, number>
  missing_canvas_blocks: PenaltyCount[]
  recurring_penalties: PenaltyCount[]
  needs_human_review_count: number
}
interface DifficultyOverview {
  threshold_pct: number
  students: StudentDifficulty[]
  cohort_weak_objectives: CohortObjective[]
  cohort_common_penalties: PenaltyCount[]
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

const BLOOM: Record<Locale, Record<number, string>> = {
  de: { 2: 'Verstehen', 3: 'Anwenden', 4: 'Analysieren', 5: 'Evaluieren', 6: 'Synthese' },
  en: { 2: 'Understand', 3: 'Apply', 4: 'Analyze', 5: 'Evaluate', 6: 'Synthesize' },
}
const OBJECTIVE_LABELS: Record<string, string> = {
  analyse: 'Analyse',
  evaluieren: 'Evaluieren',
  integration: 'Integration',
  kpi: 'KPI',
  reflexion: 'Reflexion',
  transfer: 'Transfer',
  'trade-off': 'Trade-off',
}

const DASHBOARD_TEXT = {
  de: {
    eyebrow: 'Lerner-Dashboard',
    title: 'Dashboard',
    students: 'Studierende',
    submissions: 'Submissions',
    averageScore: 'Ø Score',
    averageCanvas: 'Ø Business Model Canvas',
    exemplars: 'Exemplars',
    reviewFallback: 'Review/Fallback',
    byBloom: 'Nach Bloom-Stufe',
    byTp: 'Nach TP',
    weakestObjectives: 'Schwächste Lernziele',
    studentCount: (count: number) => `Studierende (${count})`,
    searchPlaceholder: 'Matrikelnummer suchen...',
    studentId: 'Matrikelnummer',
    review: 'Review',
    noData: 'Noch keine Daten.',
    difficulties: 'Fehlerquellen',
    difficultiesHint: (t: number) => `Wo Studierende Schwierigkeiten haben (Schwelle: unter ${t.toFixed(0)} %). Grundlage: individuelle Vorbereitung im Tool.`,
    cohortObjectives: 'Lernziele mit den meisten Betroffenen',
    cohortPenalties: 'Häufigste Schwächen (Kohorte)',
    below: (b: number, total: number) => `${b} von ${total} unter Schwelle`,
    attention: { high: 'Hoher Bedarf', medium: 'Beobachten', low: 'Unauffällig' },
    reasons: {
      low_avg: 'Ø unter 50 %',
      low_latest: 'Letzte Abgabe unter 45 %',
      multiple_weak_objectives: 'Mehrere schwache Lernziele',
      weak_objective: 'Ein schwaches Lernziel',
      weak_bloom: 'Schwache Bloom-Stufe(n)',
      needs_review: 'Evaluator unsicher — Antwort selbst ansehen',
    } as Record<string, string>,
    weakObjectives: 'Schwache Lernziele',
    weakBlooms: 'Schwache Bloom-Stufen',
    missingBlocks: 'Fehlende Canvas-Blöcke',
    recurringPenalties: 'Wiederkehrende Schwächen',
    lastSubmission: 'Letzte Abgabe',
    noDifficulties: 'Keine auffälligen Schwierigkeiten.',
  },
  en: {
    eyebrow: 'Learning dashboard',
    title: 'Dashboard',
    students: 'Students',
    submissions: 'Submissions',
    averageScore: 'Avg. score',
    averageCanvas: 'Avg. Business Model Canvas',
    exemplars: 'Exemplars',
    reviewFallback: 'Review/Fallback',
    byBloom: 'By Bloom level',
    byTp: 'By TP',
    weakestObjectives: 'Weakest learning objectives',
    studentCount: (count: number) => `Students (${count})`,
    searchPlaceholder: 'Search participant ID...',
    studentId: 'Participant ID',
    review: 'Review',
    noData: 'No data yet.',
    difficulties: 'Difficulty insights',
    difficultiesHint: (t: number) => `Where students struggle (threshold: below ${t.toFixed(0)}%). Based on individual preparation in the tool.`,
    cohortObjectives: 'Objectives with most affected students',
    cohortPenalties: 'Most common weaknesses (cohort)',
    below: (b: number, total: number) => `${b} of ${total} below threshold`,
    attention: { high: 'Needs attention', medium: 'Watch', low: 'On track' },
    reasons: {
      low_avg: 'Avg. below 50%',
      low_latest: 'Latest submission below 45%',
      multiple_weak_objectives: 'Multiple weak objectives',
      weak_objective: 'One weak objective',
      weak_bloom: 'Weak Bloom level(s)',
      needs_review: 'Evaluator uncertain — review the answer yourself',
    } as Record<string, string>,
    weakObjectives: 'Weak objectives',
    weakBlooms: 'Weak Bloom levels',
    missingBlocks: 'Missing canvas blocks',
    recurringPenalties: 'Recurring weaknesses',
    lastSubmission: 'Latest submission',
    noDifficulties: 'No notable difficulties.',
  },
} satisfies Record<Locale, {
  eyebrow: string
  title: string
  students: string
  submissions: string
  averageScore: string
  averageCanvas: string
  exemplars: string
  reviewFallback: string
  byBloom: string
  byTp: string
  weakestObjectives: string
  studentCount: (count: number) => string
  searchPlaceholder: string
  studentId: string
  review: string
  noData: string
  difficulties: string
  difficultiesHint: (threshold: number) => string
  cohortObjectives: string
  cohortPenalties: string
  below: (below: number, total: number) => string
  attention: Record<'high' | 'medium' | 'low', string>
  reasons: Record<string, string>
  weakObjectives: string
  weakBlooms: string
  missingBlocks: string
  recurringPenalties: string
  lastSubmission: string
  noDifficulties: string
}>

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
  const [language] = useLanguage()
  const [overview, setOverview] = useState<Overview | null>(null)
  const [students, setStudents] = useState<StudentRow[]>([])
  const [difficulties, setDifficulties] = useState<DifficultyOverview | null>(null)
  const [expandedStudent, setExpandedStudent] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const text = DASHBOARD_TEXT[language]

  useEffect(() => {
    sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'teacher')
    teacherFetch<Overview>('/dashboard/overview').then(setOverview)
    teacherFetch<StudentRow[]>('/dashboard/students').then(setStudents)
    teacherFetch<DifficultyOverview>('/dashboard/difficulties').then(setDifficulties)
  }, [])

  const filtered = students.filter(s => s.matrikelnummer.includes(search))

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-5xl mx-auto">
        <div className="mb-12">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
            {text.eyebrow}
          </p>
          <h1 className="font-display text-5xl leading-none">{text.title}</h1>
        </div>

        <div className="divider mb-10" />

        {overview && (
          <>
            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-6 mb-12">
              {[
                { label: text.students, value: overview.total_students, icon: <Users size={14} /> },
                { label: text.submissions, value: overview.total_submissions, icon: <TrendingUp size={14} /> },
                { label: text.averageScore, value: `${overview.avg_percentage.toFixed(0)}%`, icon: null },
                { label: text.averageCanvas, value: `${overview.avg_canvas_alignment_pct.toFixed(0)}%`, icon: null },
                { label: text.exemplars, value: overview.exemplar_submissions_count, icon: null },
                {
                  label: text.reviewFallback,
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
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>{text.byBloom}</p>
                <div className="flex flex-col gap-3">
                  {Object.entries(overview.by_bloom).map(([lvl, pct]) => (
                    <MiniBar key={lvl} pct={pct} label={BLOOM[language][Number(lvl)] ?? `Bloom ${lvl}`} />
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>{text.byTp}</p>
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
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>{text.weakestObjectives}</p>
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

        {/* Fehlerquellen / Difficulty insights */}
        {difficulties && difficulties.students.length > 0 && (
          <div className="mb-14">
            <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>{text.difficulties}</p>
            <p className="text-xs mb-6" style={{ color: 'var(--muted)' }}>{text.difficultiesHint(difficulties.threshold_pct)}</p>

            {/* Kohorte */}
            <div className="grid grid-cols-2 gap-6 mb-8">
              <div className="p-5" style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.12)' }}>
                <p className="text-xs tracking-widest uppercase mb-4" style={{ color: 'var(--muted)' }}>{text.cohortObjectives}</p>
                {difficulties.cohort_weak_objectives.filter(o => o.students_below > 0).slice(0, 6).map(o => (
                  <div key={o.tag} className="flex items-center justify-between py-1.5">
                    <span className="text-sm">{objectiveLabel(o.tag)}</span>
                    <span className="text-xs" style={{ color: o.students_below / o.students_total > 0.4 ? '#c0392b' : 'var(--muted)' }}>
                      {text.below(o.students_below, o.students_total)} · Ø {o.avg_pct.toFixed(0)}%
                    </span>
                  </div>
                ))}
                {difficulties.cohort_weak_objectives.every(o => o.students_below === 0) && (
                  <p className="text-xs" style={{ color: 'var(--muted)' }}>{text.noDifficulties}</p>
                )}
              </div>
              <div className="p-5" style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.12)' }}>
                <p className="text-xs tracking-widest uppercase mb-4" style={{ color: 'var(--muted)' }}>{text.cohortPenalties}</p>
                {difficulties.cohort_common_penalties.slice(0, 6).map(p => (
                  <div key={p.text} className="flex items-start justify-between gap-3 py-1.5">
                    <span className="text-xs leading-5">{p.text}</span>
                    <span className="text-xs font-medium shrink-0" style={{ color: 'var(--muted)' }}>×{p.count}</span>
                  </div>
                ))}
                {difficulties.cohort_common_penalties.length === 0 && (
                  <p className="text-xs" style={{ color: 'var(--muted)' }}>{text.noDifficulties}</p>
                )}
              </div>
            </div>

            {/* Pro Studierendem */}
            <div className="divider" />
            {difficulties.students.map(s => {
              const attentionColor = s.attention_level === 'high' ? '#c0392b' : s.attention_level === 'medium' ? '#ad3f2b' : 'var(--muted)'
              const attentionBg = s.attention_level === 'high' ? 'rgba(192,57,43,0.1)' : s.attention_level === 'medium' ? 'rgba(173,63,43,0.08)' : 'rgba(53,40,30,0.06)'
              const open = expandedStudent === s.matrikelnummer
              return (
                <div key={s.matrikelnummer}>
                  <button
                    onClick={() => setExpandedStudent(open ? null : s.matrikelnummer)}
                    className="w-full flex items-center justify-between py-3 px-2 text-left"
                  >
                    <div className="flex items-center gap-4 flex-wrap">
                      <span className="font-mono text-xs">{s.matrikelnummer}</span>
                      <span className="text-xs px-2 py-0.5" style={{ background: attentionBg, color: attentionColor }}>
                        {text.attention[s.attention_level]}
                      </span>
                      {s.weak_objectives.slice(0, 3).map(o => (
                        <span key={o.tag} className="text-xs px-2 py-0.5" style={{ background: 'rgba(53,40,30,0.07)', color: 'var(--ink)' }}>
                          {objectiveLabel(o.tag)} {o.avg_pct.toFixed(0)}%
                        </span>
                      ))}
                    </div>
                    <span className="text-xs shrink-0" style={{ color: 'var(--muted)' }}>
                      Ø {s.avg_percentage.toFixed(0)}%{s.latest_percentage != null && ` · ${text.lastSubmission}: ${s.latest_percentage.toFixed(0)}%`}
                    </span>
                  </button>

                  {open && (
                    <div className="px-2 pb-4 flex flex-col gap-3">
                      <div className="flex flex-wrap gap-2">
                        {s.attention_reasons.map(r => (
                          <span key={r} className="text-xs px-2 py-0.5" style={{ background: attentionBg, color: attentionColor }}>
                            {text.reasons[r] ?? r}
                          </span>
                        ))}
                      </div>
                      {Object.keys(s.weak_blooms).length > 0 && (
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>
                          {text.weakBlooms}: {Object.entries(s.weak_blooms).map(([lvl, pct]) => `${BLOOM[language][Number(lvl)] ?? `Bloom ${lvl}`} (${pct.toFixed(0)}%)`).join(', ')}
                        </p>
                      )}
                      {s.missing_canvas_blocks.length > 0 && (
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>
                          {text.missingBlocks}: {s.missing_canvas_blocks.map(b => `${objectiveLabel(b.text)} (×${b.count})`).join(', ')}
                        </p>
                      )}
                      {s.recurring_penalties.length > 0 && (
                        <div>
                          <p className="text-xs font-medium mb-1">{text.recurringPenalties}</p>
                          {s.recurring_penalties.map(p => (
                            <p key={p.text} className="text-xs leading-5" style={{ color: 'var(--muted)' }}>
                              – {p.text} {p.count > 1 && <span>×{p.count}</span>}
                            </p>
                          ))}
                        </div>
                      )}
                      {s.weak_objectives.length === 0 && s.recurring_penalties.length === 0 && Object.keys(s.weak_blooms).length === 0 && (
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>{text.noDifficulties}</p>
                      )}
                    </div>
                  )}
                  <div className="divider" />
                </div>
              )
            })}
          </div>
        )}

        {/* Student table */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <p className="text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
              {text.studentCount(filtered.length)}
            </p>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={text.searchPlaceholder}
              className="px-3 py-1.5 text-sm bg-transparent outline-none"
              style={{ border: '1px solid rgba(53,40,30,0.2)', color: 'var(--ink)', width: '220px' }}
            />
          </div>

          <div className="divider mb-0" />
          <div className="grid text-xs font-medium tracking-wide uppercase py-3 px-2" style={{ color: 'var(--muted)', gridTemplateColumns: '2fr 1fr 1fr 1fr 1fr 1fr 1fr' }}>
            <span>{text.studentId}</span>
            <span className="text-right">{text.submissions}</span>
            <span className="text-right">{text.averageScore}</span>
            <span className="text-right">{text.review}</span>
            <span className="text-right">TP 1</span>
            <span className="text-right">TP 2</span>
            <span className="text-right">TP 3</span>
          </div>
          <div className="divider" />

          {filtered.length === 0 ? (
            <p className="py-10 text-sm text-center" style={{ color: 'var(--muted)' }}>{text.noData}</p>
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
