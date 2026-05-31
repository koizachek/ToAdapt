'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import Nav from '@/components/Nav'
import { apiFetch } from '@/lib/api'
import { ArrowLeft } from 'lucide-react'

interface QuestionScore {
  question_id: string; bloom_level: number
  max_points: number; awarded_points: number
  feedback: string; learning_objective_tags: string[]
}
interface SubmissionResult {
  submission_id: string; case_id: string
  total_points: number; max_points: number; percentage: number
  scores: QuestionScore[]; overall_feedback: string
}

const BLOOM: Record<number, string> = { 2: 'Verstehen', 3: 'Anwenden', 4: 'Analysieren', 5: 'Evaluieren', 6: 'Synthese' }

function ScoreBar({ pct }: { pct: number }) {
  return (
    <div className="h-1.5 w-full rounded-none" style={{ background: 'rgba(53,40,30,0.1)' }}>
      <div
        className="h-full transition-all duration-700"
        style={{ width: `${pct}%`, background: pct >= 70 ? 'var(--accent)' : pct >= 45 ? 'var(--ink)' : '#c0392b' }}
      />
    </div>
  )
}

export default function ResultsPage() {
  const { submissionId } = useParams<{ submissionId: string }>()
  const [result, setResult] = useState<SubmissionResult | null>(null)

  useEffect(() => {
    sessionStorage.setItem('app_mode', 'student')
    // Results are stored after submit — re-fetch from the backend
    // For MVP: stored in sessionStorage by the case page
    const stored = sessionStorage.getItem(`result_${submissionId}`)
    if (stored) { setResult(JSON.parse(stored)); return }
    // Fallback: attempt re-evaluation endpoint (future)
  }, [submissionId])

  if (!result) return (
    <>
      <Nav />
      <main className="pt-32 px-8 max-w-2xl mx-auto">
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Ergebnis wird geladen…
        </p>
      </main>
    </>
  )

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-2xl mx-auto">

        <Link href="/cases" className="inline-flex items-center gap-2 text-xs mb-10 hover:text-[var(--accent)] transition-colors" style={{ color: 'var(--muted)' }}>
          <ArrowLeft size={12} /> Zurück zu Cases
        </Link>

        {/* Score header */}
        <div className="mb-12">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>Ergebnis</p>
          <div className="flex items-end gap-4 mb-4">
            <span className="font-display leading-none" style={{ fontSize: '5rem', color: 'var(--ink)' }}>
              {result.percentage.toFixed(0)}
            </span>
            <span className="font-display text-3xl mb-3" style={{ color: 'var(--muted)' }}>%</span>
            <span className="text-sm mb-3" style={{ color: 'var(--muted)' }}>
              {result.total_points} / {result.max_points} Pkt
            </span>
          </div>
          <ScoreBar pct={result.percentage} />
        </div>

        <div className="divider mb-10" />

        {/* Overall feedback */}
        <div className="mb-12 p-5" style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.12)' }}>
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>Gesamteinschätzung</p>
          <p className="text-sm leading-7">{result.overall_feedback}</p>
        </div>

        {/* Per-question scores */}
        <div className="flex flex-col gap-8">
          <p className="text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>Fragen im Detail</p>
          {result.scores.map((s, i) => (
            <div key={s.question_id}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono" style={{ color: 'var(--muted)' }}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="text-xs px-2 py-0.5" style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}>
                    {BLOOM[s.bloom_level] ?? `Bloom ${s.bloom_level}`}
                  </span>
                </div>
                <span className="text-sm font-medium">
                  {s.awarded_points} <span style={{ color: 'var(--muted)' }}>/ {s.max_points}</span>
                </span>
              </div>
              <ScoreBar pct={(s.awarded_points / s.max_points) * 100} />
              <p className="mt-3 text-sm leading-6" style={{ color: 'var(--ink)', opacity: 0.8 }}>
                {s.feedback}
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                {s.learning_objective_tags.map(tag => (
                  <span key={tag} className="text-xs px-2 py-0.5" style={{ border: '1px solid rgba(53,40,30,0.15)', color: 'var(--muted)' }}>
                    {tag}
                  </span>
                ))}
              </div>
              {i < result.scores.length - 1 && <div className="divider mt-6" />}
            </div>
          ))}
        </div>
      </main>
    </>
  )
}
