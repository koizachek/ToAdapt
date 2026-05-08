'use client'

import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import clsx from 'clsx'
import { BookOpenText, FileText, MessageSquare, Send } from 'lucide-react'
import Nav from '@/components/Nav'
import { apiFetch } from '@/lib/api'

interface CaseSection { section_id: string; title: string; content: string }
interface CaseExhibit { exhibit_id: string; title: string; content: string; exhibit_type: string }
interface CaseQuestion { question_id: string; phase: number; bloom_level: number; text: string; max_points: number }
interface Case {
  case_id: string
  title: string
  industry: string
  country: string
  tagline: string
  sections: CaseSection[]
  exhibits: CaseExhibit[]
  questions: CaseQuestion[]
}
interface ChatMsg { role: 'user' | 'agent'; content: string; agent_type?: string }
interface GlossaryTerm {
  term: string
  explanation: string
  starterPrompt: string
}

const AGENT_LABEL: Record<string, string> = {
  metacognitive: 'Reflexion',
  strategic: 'Strategie',
  conceptual: 'Konzept',
  procedural: 'Format',
}

const CASE_GLOSSARY: Record<string, GlossaryTerm[]> = {
  'alpes-bank-genai-001': [
    {
      term: 'Wertschöpfungskette',
      explanation: 'Beschreibt die zusammenhängenden Aktivitäten, mit denen ein Unternehmen über mehrere Schritte hinweg Wert für Kundinnen und Kunden erzeugt.',
      starterPrompt: 'Erkläre mir im Kontext dieses Cases den Begriff "Wertschöpfungskette" und warum er strategisch wichtiger ist als die reine Optimierung einzelner Aufgaben.',
    },
    {
      term: 'Silos',
      explanation: 'Organisatorische Abschottungen zwischen Bereichen, die Informationsfluss, Zusammenarbeit und gemeinsame Verantwortung erschweren.',
      starterPrompt: 'Hilf mir zu verstehen, was mit "Silos" in diesem Case gemeint ist und warum sie für GenAI-getriebene Prozessveränderungen problematisch sind.',
    },
    {
      term: 'Governance-Modell',
      explanation: 'Legt fest, wer entscheidet, wer kontrolliert und nach welchen Regeln Technologie verantwortungsvoll betrieben wird.',
      starterPrompt: 'Erkläre mir das Governance-Modell in diesem Case und welche organisatorischen Fähigkeiten dafür aufgebaut werden müssen.',
    },
    {
      term: 'Kontrollinstanz',
      explanation: 'Eine Rolle oder Person, die Ergebnisse prüft, Fehler abfängt und Verantwortung für die Qualität übernimmt.',
      starterPrompt: 'Was bedeutet "letzte Kontrollinstanz" hier konkret und warum bleibt sie trotz GenAI für Alpes Bank wichtig?',
    },
    {
      term: 'Rollout',
      explanation: 'Die schrittweise Einführung eines Systems im realen Betrieb, oft mit klar definiertem Umfang und Risikobegrenzung.',
      starterPrompt: 'Erkläre mir, was ein begrenzter Rollout im Fall Alpes Bank bedeutet und welche Vor- und Nachteile diese Entscheidung hat.',
    },
    {
      term: 'Anwendungsfall',
      explanation: 'Ein klar umrissener Einsatzbereich, in dem Technologie ein konkretes Problem lösen oder Nutzen stiften soll.',
      starterPrompt: 'Hilf mir, den Begriff "Anwendungsfall" im Kontext der drei GenAI-Optionen von Alpes Bank sauber einzuordnen.',
    },
    {
      term: 'MVP',
      explanation: 'Ein minimal funktionsfähiges Produkt, das den Kernnutzen schnell testbar macht, ohne schon vollständig ausgereift zu sein.',
      starterPrompt: 'Erkläre mir, was ein MVP in diesem Case bedeutet und welche Risiken entstehen, wenn man zu früh auf Geschwindigkeit setzt.',
    },
  ],
}

const INITIAL_AGENT_MESSAGE = 'Hallo! Ich bin dein Lernbegleiter für diesen Case. Markierte Fachbegriffe starten direkt eine kontextbezogene Diskussion. Wo möchtest du einsteigen?'

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function splitParagraphs(content: string) {
  return content.split(/\n\s*\n/).filter(Boolean)
}

function buildGlossaryMatcher(terms: GlossaryTerm[]) {
  if (!terms.length) return null
  const sortedTerms = [...terms].sort((a, b) => b.term.length - a.term.length)
  return new RegExp(`(${sortedTerms.map(({ term }) => escapeRegExp(term)).join('|')})`, 'gi')
}

function renderRichText(
  text: string,
  glossaryMap: Map<string, GlossaryTerm>,
  glossaryPattern: RegExp | null,
  activeTerm: string | null,
  onDiscuss: (term: GlossaryTerm) => void,
) {
  if (!glossaryPattern) return text

  return text.split(glossaryPattern).filter(Boolean).map((part, index) => {
    const match = glossaryMap.get(part.toLowerCase())
    if (!match) return <Fragment key={`${part}-${index}`}>{part}</Fragment>

    return (
      <GlossaryChip
        key={`${match.term}-${index}`}
        term={match}
        active={activeTerm === match.term}
        onDiscuss={onDiscuss}
      />
    )
  })
}

function GlossaryChip({
  term,
  active,
  onDiscuss,
}: {
  term: GlossaryTerm
  active: boolean
  onDiscuss: (term: GlossaryTerm) => void
}) {
  const [open, setOpen] = useState(false)

  return (
    <span
      className="relative inline-flex align-baseline"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        onClick={() => onDiscuss(term)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="mx-0.5 inline-flex items-center rounded-[4px] px-1.5 py-0.5 text-left text-[0.95em] font-medium transition-colors"
        style={active
          ? { background: 'var(--accent)', color: 'var(--white)' }
          : { background: 'rgba(21,99,61,0.14)', color: 'var(--accent)' }}
        aria-label={`${term.term} mit dem Lernagenten besprechen`}
      >
        {term.term}
      </button>

      <div
        className={clsx(
          'pointer-events-none absolute left-0 top-full z-20 mt-2 w-72 origin-top-left rounded-xl border px-4 py-3 text-sm shadow-sm transition-all duration-150',
          open ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0',
        )}
        style={{
          background: 'var(--white)',
          borderColor: 'rgba(53,40,30,0.12)',
          color: 'var(--ink)',
        }}
      >
        <div className="mb-2 flex items-start gap-2">
          <MessageSquare size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--accent)' }} />
          <div>
            <p className="text-xs font-semibold tracking-[0.12em] uppercase" style={{ color: 'var(--muted)' }}>
              Begriff im Kontext
            </p>
            <p className="mt-1 text-sm leading-6">{term.explanation}</p>
          </div>
        </div>

        <button
          type="button"
          onMouseDown={e => e.preventDefault()}
          onClick={() => onDiscuss(term)}
          className="pointer-events-auto mt-1 inline-flex items-center gap-2 text-xs font-medium tracking-wide"
          style={{ color: 'var(--accent)' }}
        >
          <BookOpenText size={14} />
          Mit Agent besprechen
        </button>
      </div>
    </span>
  )
}

export default function CasePage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [caseData, setCase] = useState<Case | null>(null)
  const [tab, setTab] = useState<'case' | 'questions'>('case')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submissionId, setSubmissionId] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [chat, setChat] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState('')
  const [sending, setSending] = useState(false)
  const [activeTerm, setActiveTerm] = useState<string | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const chatPanelRef = useRef<HTMLElement>(null)
  const historyRef = useRef<{ role: string; content: string }[]>([])

  const matrikel = typeof window !== 'undefined' ? sessionStorage.getItem('matrikelnummer') ?? '' : ''
  const userId = typeof window !== 'undefined' ? sessionStorage.getItem('user_id') ?? 'u_anon' : 'u_anon'

  useEffect(() => {
    apiFetch<Case>(`/admin/cases/${id}`).then(setCase)
  }, [id])

  useEffect(() => {
    if (!id || !userId) return

    apiFetch<{ submission_id: string }>('/submissions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, matrikelnummer: matrikel, case_id: id, target_tp: 1 }),
    }).then(r => setSubmissionId(r.submission_id))

    apiFetch<{ session_id: string }>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, case_id: id }),
    }).then(r => {
      setSessionId(r.session_id)
      historyRef.current = []
      setChat([{ role: 'agent', content: INITIAL_AGENT_MESSAGE, agent_type: 'metacognitive' }])
    }).catch(console.error)
  }, [id, matrikel, userId])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat, sending])

  const glossaryTerms = useMemo(() => CASE_GLOSSARY[id] ?? [], [id])
  const glossaryMap = useMemo(
    () => new Map(glossaryTerms.map(term => [term.term.toLowerCase(), term])),
    [glossaryTerms],
  )
  const glossaryPattern = useMemo(() => buildGlossaryMatcher(glossaryTerms), [glossaryTerms])

  const sendChatMessage = async (content: string) => {
    if (!content.trim() || !sessionId || sending) return false

    const message = content.trim()
    setSending(true)
    setChatInput('')
    setChat(current => [...current, { role: 'user', content: message }])
    historyRef.current = [...historyRef.current, { role: 'user', content: message }]

    try {
      const res = await apiFetch<{ agent_type: string; content: string }>(
        `/sessions/${sessionId}/chat`,
        { method: 'POST', body: JSON.stringify({ content: message, history: historyRef.current.slice(-10) }) },
      )
      historyRef.current = [...historyRef.current, { role: 'assistant', content: res.content }]
      setChat(current => [...current, { role: 'agent', content: res.content, agent_type: res.agent_type }])
      return true
    } catch (error: any) {
      const messageText = error?.message || 'Unbekannter Fehler'
      setChat(current => [...current, { role: 'agent', content: `Fehler: ${messageText}`, agent_type: 'metacognitive' }])
      return false
    } finally {
      setSending(false)
    }
  }

  const sendChat = async () => {
    await sendChatMessage(chatInput)
  }

  const startGlossaryChat = async (term: GlossaryTerm) => {
    setActiveTerm(term.term)
    chatPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })

    if (!sessionId || sending) {
      setChatInput(term.starterPrompt)
      return
    }

    await sendChatMessage(term.starterPrompt)
  }

  const saveAnswer = (qid: string, text: string) => {
    if (!submissionId) return
    apiFetch(`/submissions/${submissionId}/answer`, {
      method: 'POST',
      body: JSON.stringify({ question_id: qid, answer_text: text }),
    })
  }

  const handleSubmit = async () => {
    if (!submissionId) return
    const result = await apiFetch<any>(`/submissions/${submissionId}/submit`, { method: 'POST' })
    sessionStorage.setItem(`result_${submissionId}`, JSON.stringify(result))
    router.push(`/results/${submissionId}`)
  }

  if (!caseData) {
    return (
      <>
        <Nav />
        <main className="px-8 pt-32 text-sm" style={{ color: 'var(--muted)' }}>Wird geladen…</main>
      </>
    )
  }

  const tabs = [
    { key: 'case' as const, label: 'Task Materials', icon: <FileText size={14} /> },
    { key: 'questions' as const, label: 'Fragen', icon: <FileText size={14} /> },
  ]

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-[1400px] px-6 pb-12 pt-24 lg:px-8">
        <div className="py-6">
          <p className="mb-1 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
            {caseData.industry} · {caseData.country}
          </p>
          <h1 className="font-display text-3xl leading-tight">{caseData.title}</h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--muted)' }}>{caseData.tagline}</p>
        </div>

        <div className="divider" />

        <div className="flex gap-0 border-b" style={{ borderColor: 'rgba(53,40,30,0.12)' }}>
          {tabs.map(t => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={clsx(
                'flex items-center gap-2 border-b-2 -mb-px px-5 py-3 text-xs font-medium tracking-wide transition-all',
                tab === t.key ? 'border-[var(--accent)]' : 'border-transparent',
              )}
              style={{ color: tab === t.key ? 'var(--accent)' : 'var(--muted)' }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        <div className="mt-8 grid items-start gap-8 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section className="min-w-0">
            {tab === 'case' && (
              <div className="flex flex-col gap-10 pr-0 xl:pr-4">
                {caseData.sections.map(section => (
                  <section key={section.section_id}>
                    <h2 className="mb-3 text-base font-medium">{section.title}</h2>
                    <div className="flex flex-col gap-5 text-sm leading-8">
                      {splitParagraphs(section.content).map((paragraph, index) => (
                        <p key={`${section.section_id}-${index}`}>
                          {renderRichText(paragraph, glossaryMap, glossaryPattern, activeTerm, startGlossaryChat)}
                        </p>
                      ))}
                    </div>
                  </section>
                ))}

                {caseData.exhibits.length > 0 && (
                  <section>
                    <h2 className="mb-5 text-base font-medium">Exhibits</h2>
                    <div className="flex flex-col gap-6">
                      {caseData.exhibits.map(exhibit => (
                        <div
                          key={exhibit.exhibit_id}
                          className="rounded-2xl p-5"
                          style={{ border: '1px solid rgba(53,40,30,0.15)', background: 'rgba(250,250,248,0.45)' }}
                        >
                          <p className="mb-3 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
                            {exhibit.title}
                          </p>
                          <pre
                            className="overflow-x-auto whitespace-pre-wrap text-xs leading-6"
                            style={{ fontFamily: 'inherit' }}
                          >
                            {exhibit.content}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            )}

            {tab === 'questions' && (
              <div className="flex max-w-3xl flex-col gap-8 pr-0 xl:pr-4">
                {caseData.questions.map((question, index) => (
                  <div key={question.question_id}>
                    <div className="mb-3 flex items-start justify-between gap-4">
                      <div className="flex items-start gap-4">
                        <span className="mt-0.5 shrink-0 font-mono text-xs" style={{ color: 'var(--muted)' }}>
                          {String(index + 1).padStart(2, '0')}
                        </span>
                        <p className="text-sm leading-6">{question.text}</p>
                      </div>
                      <span
                        className="shrink-0 rounded-full px-2.5 py-1 text-xs"
                        style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                      >
                        {question.max_points} Pkt
                      </span>
                    </div>

                    <textarea
                      value={answers[question.question_id] ?? ''}
                      onChange={event => setAnswers(current => ({ ...current, [question.question_id]: event.target.value }))}
                      onBlur={event => saveAnswer(question.question_id, event.target.value)}
                      rows={6}
                      placeholder="Deine Antwort…"
                      className="ml-8 w-full resize-none rounded-2xl bg-transparent px-4 py-3 text-sm outline-none transition-all"
                      style={{ border: '1px solid rgba(53,40,30,0.2)', color: 'var(--ink)' }}
                      onFocus={event => { event.currentTarget.style.borderColor = 'var(--accent)' }}
                      onBlurCapture={event => { event.currentTarget.style.borderColor = 'rgba(53,40,30,0.2)' }}
                    />
                  </div>
                ))}

                <div className="divider" />

                <button
                  type="button"
                  onClick={handleSubmit}
                  className="self-start rounded-full px-6 py-3 text-sm font-medium tracking-wide transition-all duration-200"
                  style={{ background: 'var(--ink)', color: 'var(--white)' }}
                  onMouseEnter={event => { event.currentTarget.style.background = 'var(--accent)' }}
                  onMouseLeave={event => { event.currentTarget.style.background = 'var(--ink)' }}
                >
                  Abgeben & auswerten
                </button>
              </div>
            )}
          </section>

          <aside
            ref={chatPanelRef}
            className="xl:sticky xl:top-28"
          >
            <div
              className="overflow-hidden rounded-[28px] border"
              style={{
                background: 'rgba(250,250,248,0.7)',
                borderColor: 'rgba(53,40,30,0.12)',
                backdropFilter: 'blur(10px)',
              }}
            >
              <div className="border-b px-5 py-4" style={{ borderColor: 'rgba(53,40,30,0.12)' }}>
                <div className="flex items-center gap-3">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-full"
                    style={{ background: 'rgba(21,99,61,0.12)', color: 'var(--accent)' }}
                  >
                    <MessageSquare size={18} />
                  </div>
                  <div>
                    <p className="text-xs tracking-[0.16em] uppercase" style={{ color: 'var(--muted)' }}>
                      Lernchat
                    </p>
                    <p className="text-sm font-medium">Direkt neben dem Material</p>
                  </div>
                </div>

                <p className="mt-3 text-sm leading-6" style={{ color: 'var(--muted)' }}>
                  Markierte Begriffe starten eine gezielte Diskussion, ohne dass du den Lesekontext verlierst.
                </p>

                {activeTerm && (
                  <div
                    className="mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs"
                    style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                  >
                    <BookOpenText size={13} />
                    Aktives Thema: {activeTerm}
                  </div>
                )}
              </div>

              <div className="flex h-[28rem] flex-col">
                <div className="flex-1 overflow-y-auto px-5 py-4">
                  <div className="flex flex-col gap-4">
                    {chat.map((message, index) => (
                      <div key={index} className={clsx('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                        {message.role === 'agent' && (
                          <span className="mr-2 mt-2 shrink-0 text-xs font-medium" style={{ color: 'var(--accent)' }}>
                            {AGENT_LABEL[message.agent_type ?? ''] ?? 'Agent'}
                          </span>
                        )}

                        <div
                          className="max-w-[18rem] rounded-2xl px-4 py-3 text-sm leading-6"
                          style={message.role === 'user'
                            ? { background: 'var(--ink)', color: 'var(--white)' }
                            : { background: 'var(--surface)', color: 'var(--ink)', border: '1px solid rgba(53,40,30,0.12)' }}
                        >
                          {message.content}
                        </div>
                      </div>
                    ))}

                    {sending && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs" style={{ color: 'var(--accent)' }}>Agent</span>
                        <span className="text-xs" style={{ color: 'var(--muted)' }}>schreibt…</span>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>
                </div>

                <div className="border-t px-4 py-4" style={{ borderColor: 'rgba(53,40,30,0.12)' }}>
                  <div className="flex items-stretch overflow-hidden rounded-full" style={{ border: '1px solid rgba(53,40,30,0.2)' }}>
                    <input
                      value={chatInput}
                      onChange={event => setChatInput(event.target.value)}
                      onKeyDown={event => {
                        if (event.key === 'Enter' && !event.shiftKey) {
                          event.preventDefault()
                          void sendChat()
                        }
                      }}
                      placeholder="Frag den Agenten zum Material…"
                      className="min-w-0 flex-1 bg-transparent px-4 py-3 text-sm outline-none"
                      style={{ color: 'var(--ink)' }}
                    />
                    <button
                      type="button"
                      onClick={() => void sendChat()}
                      disabled={sending}
                      className="px-4 py-3 transition-all duration-150"
                      style={{ background: sending ? 'var(--muted)' : 'var(--ink)', color: 'var(--white)' }}
                      onMouseEnter={event => { if (!sending) event.currentTarget.style.background = 'var(--accent)' }}
                      onMouseLeave={event => { if (!sending) event.currentTarget.style.background = 'var(--ink)' }}
                    >
                      <Send size={15} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </>
  )
}
