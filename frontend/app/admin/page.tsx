'use client'

import { useEffect, useState } from 'react'
import Nav from '@/components/Nav'
import { apiFetch } from '@/lib/api'
import { Plus, Check, X, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'

interface CaseSummary { case_id: string; title: string; industry: string; difficulty: string; status: string }
interface Case extends CaseSummary {
  country: string; tagline: string
  sections: { section_id: string; title: string; content: string }[]
  exhibits: { exhibit_id: string; title: string; content: string }[]
  questions: { question_id: string; text: string; max_points: number; bloom_level: number }[]
}

const INDUSTRIES = ['Mobility', 'HealthTech', 'Retail', 'Logistics', 'EdTech', 'FinTech', 'Hospitality', 'Manufacturing']
const COUNTRIES  = ['Deutschland', 'Österreich', 'Frankreich', 'Niederlande', 'Schweden', 'Polen', 'Spanien', 'Italien']
const TP_OPTIONS = [{ value: 1, label: 'TP 1 — Analyse' }, { value: 2, label: 'TP 2 — Strategie' }, { value: 3, label: 'TP 3 — Umsetzung' }, { value: 4, label: 'TP 4 — Integration' }]

export default function AdminPage() {
  const [cases, setCases]       = useState<CaseSummary[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [detail, setDetail]     = useState<Record<string, Case>>({})
  const [generating, setGen]    = useState(false)
  const [form, setForm]         = useState({ industry: INDUSTRIES[0], country: COUNTRIES[0], target_tp: 1 })
  const [reviewer, setReviewer] = useState('')

  const load = () => apiFetch<CaseSummary[]>('/admin/cases').then(setCases)
  useEffect(() => {
    sessionStorage.setItem('app_mode', 'teacher')
    load()
  }, [])

  const generate = async () => {
    setGen(true)
    try {
      await apiFetch('/admin/cases/generate', { method: 'POST', body: JSON.stringify({ ...form, difficulty: `tp${form.target_tp}` }) })
      await load()
    } finally { setGen(false) }
  }

  const toggle = async (id: string) => {
    if (expanded === id) { setExpanded(null); return }
    setExpanded(id)
    if (!detail[id]) {
      const c = await apiFetch<Case>(`/admin/cases/${id}`)
      setDetail(d => ({ ...d, [id]: c }))
    }
  }

  const approve = async (id: string) => {
    await apiFetch(`/admin/cases/${id}/approve`, { method: 'POST', body: JSON.stringify({ reviewer: reviewer || 'Dozent' }) })
    load()
  }
  const reject = async (id: string) => {
    await apiFetch(`/admin/cases/${id}/reject`, { method: 'POST', body: JSON.stringify({ reviewer: reviewer || 'Dozent' }) })
    load()
  }

  const STATUS_STYLE: Record<string, string> = {
    draft:    'rgba(53,40,30,0.12)',
    approved: 'rgba(21,99,61,0.15)',
    rejected: 'rgba(192,57,43,0.1)',
  }
  const STATUS_LABEL: Record<string, string> = { draft: 'Entwurf', approved: 'Freigegeben', rejected: 'Abgelehnt' }

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-4xl mx-auto">
        <div className="mb-12">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>Dozenten-Interface</p>
          <h1 className="font-display text-5xl leading-none">Admin</h1>
        </div>

        <div className="divider mb-10" />

        {/* Generator form */}
        <section className="mb-14">
          <p className="text-xs tracking-widest uppercase mb-6" style={{ color: 'var(--muted)' }}>Neuen Case generieren</p>
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { label: 'Branche', key: 'industry', options: INDUSTRIES },
              { label: 'Land',    key: 'country',  options: COUNTRIES },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs mb-2 font-medium" style={{ color: 'var(--line)' }}>{f.label}</label>
                <select
                  value={(form as any)[f.key]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  className="w-full px-3 py-2.5 text-sm bg-transparent outline-none"
                  style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
                >
                  {f.options.map(o => <option key={o}>{o}</option>)}
                </select>
              </div>
            ))}
            <div>
              <label className="block text-xs mb-2 font-medium" style={{ color: 'var(--line)' }}>Ziel-TP</label>
              <select
                value={form.target_tp}
                onChange={e => setForm(p => ({ ...p, target_tp: Number(e.target.value) }))}
                className="w-full px-3 py-2.5 text-sm bg-transparent outline-none"
                style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
              >
                {TP_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <button
            onClick={generate}
            disabled={generating}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium tracking-wide transition-all duration-200"
            style={{ background: 'var(--ink)', color: 'var(--white)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'var(--ink)')}
          >
            <Plus size={14} />
            {generating ? 'Wird generiert…' : 'Case generieren'}
          </button>
        </section>

        {/* Reviewer name */}
        <div className="mb-8 flex items-center gap-4">
          <p className="text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>Reviewer</p>
          <input
            value={reviewer}
            onChange={e => setReviewer(e.target.value)}
            placeholder="Dein Name"
            className="px-3 py-1.5 text-sm bg-transparent outline-none"
            style={{ border: '1px solid rgba(53,40,30,0.2)', color: 'var(--ink)', width: '180px' }}
          />
        </div>

        {/* Case list */}
        <div className="divider mb-6" />
        <ul className="flex flex-col">
          {cases.map((c, i) => (
            <li key={c.case_id}>
              {i > 0 && <div className="divider" />}
              <div className="py-5">
                <div className="flex items-center justify-between">
                  <button onClick={() => toggle(c.case_id)} className="flex items-center gap-4 text-left flex-1 group">
                    <span className="text-xs font-mono" style={{ color: 'var(--muted)' }}>{String(i+1).padStart(2,'0')}</span>
                    <div>
                      <p className="text-sm font-medium group-hover:text-[var(--accent)] transition-colors">{c.title}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>{c.industry}</p>
                    </div>
                    {expanded === c.case_id ? <ChevronUp size={14} style={{ color: 'var(--muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--muted)' }} />}
                  </button>
                  <div className="flex items-center gap-3">
                    <span className="text-xs px-2 py-0.5" style={{ background: STATUS_STYLE[c.status], color: 'var(--ink)' }}>
                      {STATUS_LABEL[c.status] ?? c.status}
                    </span>
                    {c.status === 'draft' && (
                      <>
                        <button
                          onClick={() => approve(c.case_id)}
                          className="p-1.5 transition-all"
                          style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                          onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent)', (e.currentTarget as any).style.color = 'white')}
                          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(21,99,61,0.1)', (e.currentTarget as any).style.color = 'var(--accent)')}
                          title="Freigeben"
                        ><Check size={13} /></button>
                        <button
                          onClick={() => reject(c.case_id)}
                          className="p-1.5 transition-all"
                          style={{ background: 'rgba(192,57,43,0.08)', color: '#c0392b' }}
                          title="Ablehnen"
                        ><X size={13} /></button>
                      </>
                    )}
                  </div>
                </div>

                {/* Expanded detail */}
                {expanded === c.case_id && detail[c.case_id] && (
                  <div className="mt-5 ml-10 flex flex-col gap-5">
                    <p className="text-sm italic" style={{ color: 'var(--muted)' }}>{detail[c.case_id].tagline}</p>
                    {detail[c.case_id].sections.slice(0, 2).map(s => (
                      <div key={s.section_id}>
                        <p className="text-xs font-medium mb-1">{s.title}</p>
                        <p className="text-xs leading-5" style={{ color: 'var(--muted)' }}>{s.content.slice(0, 300)}…</p>
                      </div>
                    ))}
                    <div>
                      <p className="text-xs font-medium mb-2">Fragen ({detail[c.case_id].questions.length})</p>
                      {detail[c.case_id].questions.map((q, qi) => (
                        <p key={q.question_id} className="text-xs leading-5 mb-1" style={{ color: 'var(--muted)' }}>
                          {qi+1}. {q.text.slice(0, 120)}… <span style={{ color: 'var(--accent)' }}>({q.max_points} Pkt)</span>
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      </main>
    </>
  )
}
