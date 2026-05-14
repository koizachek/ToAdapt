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
interface ExperimentContext {
  provider?: string
  experiment_name?: string
  run_id?: string
  condition?: string
  prolific_pid?: string
  prolific_study_id?: string
  prolific_session_id?: string
  metadata?: Record<string, string>
}
interface GlossaryTerm {
  term: string
  explanation: string
  starterPrompt: string
}
interface ParsedExhibitTable {
  headers: string[]
  rows: string[][]
  notes: string[]
}
interface AnswerRequirement {
  minWords: number
  maxWords: number
}

interface CanvasBlock {
  key: string
  label: string
  hint: string
}

const AGENT_LABEL: Record<string, string> = {
  metacognitive: 'Reflexion',
  strategic: 'Strategie',
  conceptual: 'Konzept',
  procedural: 'Format',
}

const BUSINESS_MODEL_CANVAS_BLOCKS: CanvasBlock[] = [
  { key: 'value_propositions', label: 'Value Propositions', hint: 'Welchen konkreten Nutzen verspricht Alpes Bank ihren Kundinnen und Kunden?' },
  { key: 'customer_segments', label: 'Customer Segments', hint: 'Welche Kundengruppen sind besonders relevant oder betroffen?' },
  { key: 'channels', label: 'Channels', hint: 'Über welche Kanäle wird Leistung erbracht oder verändert sich der Zugang?' },
  { key: 'customer_relationships', label: 'Customer Relationships', hint: 'Wie verändert sich die Kundenbeziehung, Beratung oder das Vertrauen?' },
  { key: 'revenue_streams', label: 'Revenue Streams', hint: 'Welche Ertragslogik wird gestärkt, bedroht oder verändert?' },
  { key: 'key_resources', label: 'Key Resources', hint: 'Welche Ressourcen, Fähigkeiten, Daten oder Kompetenzen tragen die Lösung?' },
  { key: 'key_activities', label: 'Key Activities', hint: 'Welche zentralen Aktivitäten oder Prozesse müssen neu gestaltet werden?' },
  { key: 'key_partners', label: 'Key Partners', hint: 'Welche Partner spielen eine tragende Rolle für Umsetzung oder Risiko?' },
  { key: 'cost_structure', label: 'Cost Structure', hint: 'Welche Kosten-, Effizienz- oder Investitionsfolgen sind zentral?' },
]

const CASE_GLOSSARY: Record<string, GlossaryTerm[]> = {
  'alpes-bank-genai-001': [
    {
      term: 'Wertschöpfungskette',
      explanation: 'Beschreibt die zusammenhängenden Aktivitäten, mit denen ein Unternehmen über mehrere Schritte hinweg Wert für Kundinnen und Kunden erzeugt.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Wertschöpfungskette" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Silos',
      explanation: 'Organisatorische Abschottungen zwischen Bereichen, die Informationsfluss, Zusammenarbeit und gemeinsame Verantwortung erschweren.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Silos" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Governance-Modell',
      explanation: 'Legt fest, wer entscheidet, wer kontrolliert und nach welchen Regeln Technologie verantwortungsvoll betrieben wird.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Governance-Modell" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Kontrollinstanz',
      explanation: 'Eine Rolle oder Person, die Ergebnisse prüft, Fehler abfängt und Verantwortung für die Qualität übernimmt.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Kontrollinstanz" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Rollout',
      explanation: 'Die schrittweise Einführung eines Systems im realen Betrieb, oft mit klar definiertem Umfang und Risikobegrenzung.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Rollout" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Anwendungsfall',
      explanation: 'Ein klar umrissener Einsatzbereich, in dem Technologie ein konkretes Problem lösen oder Nutzen stiften soll.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Anwendungsfall" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'MVP',
      explanation: 'Ein minimal funktionsfähiges Produkt, das den Kernnutzen schnell testbar macht, ohne schon vollständig ausgereift zu sein.',
      starterPrompt: 'Erkläre mir kurz den Begriff "MVP" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
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

function getAnswerRequirement(questionIndex: number): AnswerRequirement {
  if (questionIndex <= 1) return { minWords: 50, maxWords: 200 }
  if (questionIndex <= 3) return { minWords: 100, maxWords: 200 }
  return { minWords: 150, maxWords: 200 }
}

function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

function readExperimentContext(): ExperimentContext | null {
  if (typeof window === 'undefined') return null

  try {
    return JSON.parse(sessionStorage.getItem('experiment_context') ?? 'null')
  } catch {
    return null
  }
}

function hasSentenceStructure(text: string): boolean {
  return /[.!?]/.test(text.trim())
}

function parseExhibitTable(content: string): ParsedExhibitTable | null {
  const lines = content
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)

  const pipeLines = lines.filter(line => line.includes('|'))
  if (pipeLines.length < 2) return null

  const parseRow = (line: string) =>
    line
      .split('|')
      .map(cell => cell.trim())
      .filter(Boolean)

  const headers = parseRow(pipeLines[0])
  if (headers.length < 2) return null

  const rows = pipeLines.slice(1)
    .map(parseRow)
    .filter(row => row.length >= 2)

  if (!rows.length) return null

  const notes = lines.filter(line => !line.includes('|'))

  return { headers, rows, notes }
}

function ExhibitTable({ content }: { content: string }) {
  const parsed = parseExhibitTable(content)

  if (!parsed) {
    return (
      <pre
        className="overflow-x-auto whitespace-pre-wrap text-xs leading-6"
        style={{ fontFamily: 'inherit' }}
      >
        {content}
      </pre>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              {parsed.headers.map((header, index) => (
                <th
                  key={`${header}-${index}`}
                  className="border-b px-4 py-3 text-left text-xs font-semibold tracking-[0.08em] uppercase"
                  style={{
                    borderColor: 'rgba(53,40,30,0.12)',
                    color: 'var(--muted)',
                    whiteSpace: index === 0 ? 'normal' : 'nowrap',
                  }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {parsed.rows.map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`}>
                {parsed.headers.map((_, cellIndex) => (
                  <td
                    key={`cell-${rowIndex}-${cellIndex}`}
                    className="border-b px-4 py-3 align-top text-sm"
                    style={{
                      borderColor: 'rgba(53,40,30,0.08)',
                      color: 'var(--ink)',
                      fontWeight: cellIndex === 0 ? 500 : 400,
                      whiteSpace: cellIndex === 0 ? 'normal' : 'nowrap',
                    }}
                  >
                    {row[cellIndex] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {parsed.notes.map((note, index) => (
        <p key={`note-${index}`} className="text-sm leading-7" style={{ color: 'var(--ink)' }}>
          {note}
        </p>
      ))}
    </div>
  )
}

function BusinessModelCanvasGuide() {
  return (
    <section
      className="rounded-[28px] border p-6"
      style={{
        background: 'linear-gradient(135deg, rgba(21,99,61,0.09), rgba(184,134,11,0.08))',
        borderColor: 'rgba(53,40,30,0.14)',
      }}
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="mb-2 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
            Verbindlicher Analyserahmen
          </p>
          <h2 className="font-display text-2xl leading-tight">Business Model Canvas</h2>
        </div>
        <span
          className="shrink-0 rounded-full px-3 py-1 text-xs font-medium tracking-wide"
          style={{ background: 'rgba(21,99,61,0.14)', color: 'var(--accent)' }}
        >
          Pflicht für die Bearbeitung
        </span>
      </div>

      <p className="mb-5 text-sm leading-7" style={{ color: 'var(--ink)' }}>
        Bearbeite die Fragen auf Basis des Business Model Canvas. Strukturiere deine Antwort entlang der
        relevanten Canvas-Bausteine und zeige, wie sich Entscheidung, Risiko und Wirkung auf das
        Geschäftsmodell von Alpes Bank auswirken.
      </p>

      <div className="mb-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {BUSINESS_MODEL_CANVAS_BLOCKS.map(block => (
          <div
            key={block.key}
            className="rounded-2xl px-4 py-4"
            style={{ background: 'rgba(250,250,248,0.72)', border: '1px solid rgba(53,40,30,0.1)' }}
          >
            <p className="mb-2 text-xs font-semibold tracking-[0.08em] uppercase" style={{ color: 'var(--accent)' }}>
              {block.label}
            </p>
            <p className="text-sm leading-6" style={{ color: 'var(--ink)' }}>
              {block.hint}
            </p>
          </div>
        ))}
      </div>

      <div
        className="rounded-2xl px-4 py-4 text-sm leading-7"
        style={{ background: 'rgba(53,40,30,0.05)', color: 'var(--ink)' }}
      >
        Gute Antworten nennen nicht nur Begriffe, sondern wenden die passenden Canvas-Bausteine konkret auf
        den Fall an. Entscheidend ist, wie sauber du den Zusammenhang zwischen Geschäftsmodell,
        Wettbewerb, Umsetzung und Risiko erklärst.
      </div>
    </section>
  )
}

function renderRichText(
  text: string,
  glossaryMap: Map<string, GlossaryTerm>,
  glossaryPattern: RegExp | null,
  highlightedTerms: Set<string>,
  activeTerm: string | null,
  onDiscuss: (term: GlossaryTerm) => void,
) {
  if (!glossaryPattern) return text

  return text.split(glossaryPattern).filter(Boolean).map((part, index) => {
    const match = glossaryMap.get(part.toLowerCase())
    if (!match) return <Fragment key={`${part}-${index}`}>{part}</Fragment>
    if (highlightedTerms.has(match.term)) {
      return <Fragment key={`${match.term}-plain-${index}`}>{part}</Fragment>
    }

    highlightedTerms.add(match.term)

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

      <span
        className={clsx(
          'pointer-events-none absolute left-0 top-full z-20 mt-2 w-72 origin-top-left rounded-xl border px-4 py-3 text-sm shadow-sm transition-all duration-150',
          open ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0',
        )}
        style={{
          background: 'var(--white)',
          borderColor: 'rgba(53,40,30,0.12)',
          color: 'var(--ink)',
        }}
        role="tooltip"
      >
        <span className="mb-2 flex items-start gap-2">
          <MessageSquare size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--accent)' }} />
          <span>
            <span className="text-xs font-semibold tracking-[0.12em] uppercase" style={{ color: 'var(--muted)' }}>
              Begriff im Kontext
            </span>
            <span className="mt-1 block text-sm leading-6">{term.explanation}</span>
          </span>
        </span>

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
      </span>
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
  const [submitting, setSubmitting] = useState(false)
  const [activeTerm, setActiveTerm] = useState<string | null>(null)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const chatScrollRef = useRef<HTMLDivElement>(null)
  const historyRef = useRef<{ role: string; content: string }[]>([])

  const matrikel = typeof window !== 'undefined' ? sessionStorage.getItem('matrikelnummer') ?? '' : ''
  const userId = typeof window !== 'undefined' ? sessionStorage.getItem('user_id') ?? 'u_anon' : 'u_anon'
  const experimentContext = useMemo(() => readExperimentContext(), [])

  useEffect(() => {
    apiFetch<Case>(`/admin/cases/${id}`).then(setCase)
  }, [id])

  useEffect(() => {
    if (!id || !userId) return

    apiFetch<{ submission_id: string }>('/submissions', {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        matrikelnummer: matrikel,
        case_id: id,
        target_tp: 1,
        experiment: experimentContext,
      }),
    }).then(r => setSubmissionId(r.submission_id))

    apiFetch<{ session_id: string }>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, case_id: id, experiment: experimentContext }),
    }).then(r => {
      setSessionId(r.session_id)
      historyRef.current = []
      setChat([{ role: 'agent', content: INITIAL_AGENT_MESSAGE, agent_type: 'metacognitive' }])
    }).catch(console.error)
  }, [experimentContext, id, matrikel, userId])

  useEffect(() => {
    const node = chatScrollRef.current
    if (!node) return
    node.scrollTo({ top: node.scrollHeight, behavior: 'smooth' })
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
    if (!submissionId || !caseData || submitting) return
    const invalidQuestion = caseData.questions.find((question, index) => {
      const requirement = getAnswerRequirement(index)
      const wordCount = countWords(answers[question.question_id] ?? '')
      return wordCount < requirement.minWords || wordCount > requirement.maxWords
    })

    if (invalidQuestion) {
      const questionIndex = caseData.questions.findIndex(q => q.question_id === invalidQuestion.question_id)
      const requirement = getAnswerRequirement(questionIndex)
      setSubmissionError(
        `Frage ${questionIndex + 1} muss zwischen ${requirement.minWords} und ${requirement.maxWords} Wörtern liegen.`,
      )
      return
    }

    setSubmissionError(null)
    setSubmitting(true)

    try {
      const result = await apiFetch<any>(`/submissions/${submissionId}/submit`, { method: 'POST' })
      sessionStorage.setItem(`result_${submissionId}`, JSON.stringify(result))
      router.replace('/goodbye')
    } catch (error: any) {
      setSubmissionError(error?.message || 'Die Auswertung konnte nicht abgeschlossen werden.')
    } finally {
      setSubmitting(false)
    }
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
  const highlightedTerms = new Set<string>()

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
                        <div key={`${section.section_id}-${index}`}>
                          {renderRichText(
                            paragraph,
                            glossaryMap,
                            glossaryPattern,
                            highlightedTerms,
                            activeTerm,
                            startGlossaryChat,
                          )}
                        </div>
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
                          {exhibit.exhibit_type === 'table'
                            ? <ExhibitTable content={exhibit.content} />
                            : (
                              <pre
                                className="overflow-x-auto whitespace-pre-wrap text-xs leading-6"
                                style={{ fontFamily: 'inherit' }}
                              >
                                {exhibit.content}
                              </pre>
                            )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            )}

            {tab === 'questions' && (
              <div className="flex max-w-3xl flex-col gap-8 pr-0 xl:pr-4">
                <BusinessModelCanvasGuide />

                <div
                  className="rounded-2xl px-5 py-4 text-sm leading-7"
                  style={{ background: 'rgba(21,99,61,0.08)', color: 'var(--ink)' }}
                >
                  Schreibe in ganzen Sätzen. Für Frage 1–2 gilt 50–200 Wörter, für Frage 3–4 100–200 Wörter.
                </div>

                {caseData.questions.map((question, index) => (
                  <div key={question.question_id}>
                    {(() => {
                      const requirement = getAnswerRequirement(index)
                      const answerText = answers[question.question_id] ?? ''
                      const wordCount = countWords(answerText)
                      const isWithinRange = wordCount >= requirement.minWords && wordCount <= requirement.maxWords
                      const sentenceHintVisible = answerText.trim().length > 0 && !hasSentenceStructure(answerText)

                      return (
                        <>
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
                      value={answerText}
                      onChange={event => setAnswers(current => ({ ...current, [question.question_id]: event.target.value }))}
                      onBlur={event => saveAnswer(question.question_id, event.target.value)}
                      rows={6}
                      placeholder={`Deine Antwort in ganzen Sätzen (${requirement.minWords}–${requirement.maxWords} Wörter)…`}
                      className="ml-8 w-full resize-none rounded-2xl bg-transparent px-4 py-3 text-sm outline-none transition-all"
                      style={{
                        border: `1px solid ${answerText.trim().length > 0 && !isWithinRange ? 'rgba(173,63,43,0.45)' : 'rgba(53,40,30,0.2)'}`,
                        color: 'var(--ink)',
                      }}
                      onFocus={event => { event.currentTarget.style.borderColor = 'var(--accent)' }}
                      onBlurCapture={event => {
                        event.currentTarget.style.borderColor = answerText.trim().length > 0 && !isWithinRange
                          ? 'rgba(173,63,43,0.45)'
                          : 'rgba(53,40,30,0.2)'
                      }}
                    />
                    <div className="ml-8 mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                      <span style={{ color: 'var(--muted)' }}>
                        Vorgabe: {requirement.minWords}–{requirement.maxWords} Wörter, ganze Sätze
                      </span>
                      <span style={{ color: answerText.trim().length === 0 || isWithinRange ? 'var(--accent)' : '#ad3f2b' }}>
                        {wordCount} Wörter
                      </span>
                      {sentenceHintVisible && (
                        <span style={{ color: '#ad3f2b' }}>
                          Bitte in ganzen Sätzen formulieren.
                        </span>
                      )}
                    </div>
                        </>
                      )
                    })()}
                  </div>
                ))}

                <div className="divider" />

                {submissionError && (
                  <p className="text-sm" style={{ color: '#ad3f2b' }}>
                    {submissionError}
                  </p>
                )}

                {submitting && (
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>
                    Auswertung laeuft. Bitte Seite nicht schliessen.
                  </p>
                )}

                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="self-start rounded-full px-6 py-3 text-sm font-medium tracking-wide transition-all duration-200"
                  style={{ background: submitting ? 'var(--muted)' : 'var(--ink)', color: 'var(--white)' }}
                  onMouseEnter={event => { if (!submitting) event.currentTarget.style.background = 'var(--accent)' }}
                  onMouseLeave={event => { if (!submitting) event.currentTarget.style.background = 'var(--ink)' }}
                >
                  {submitting ? 'Wird ausgewertet…' : 'Abgeben & auswerten'}
                </button>
              </div>
            )}
          </section>

          <aside className="xl:sticky xl:top-28">
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
                    <p className="text-sm font-medium">Lernchat</p>
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
                <div ref={chatScrollRef} className="flex-1 overflow-y-auto px-5 py-4">
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
