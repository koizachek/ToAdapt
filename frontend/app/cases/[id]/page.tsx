'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Nav from '@/components/Nav'
import { apiFetch } from '@/lib/api'
import { Send, MessageSquare, FileText, X } from 'lucide-react'
import clsx from 'clsx'

interface CaseSection { section_id: string; title: string; content: string }
interface CaseExhibit { exhibit_id: string; title: string; content: string; exhibit_type: string }
interface CaseQuestion { question_id: string; phase: number; bloom_level: number; text: string; max_points: number }
interface Case {
  case_id: string; title: string; industry: string; country: string; tagline: string
  sections: CaseSection[]; exhibits: CaseExhibit[]; questions: CaseQuestion[]
}

interface ChatMsg { role: 'user' | 'agent'; content: string; agent_type?: string }

const AGENT_LABEL: Record<string, string> = {
  metacognitive: 'Reflexion',
  strategic: 'Strategie',
  conceptual: 'Konzept',
  procedural: 'Format',
}

export default function CasePage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [caseData, setCase] = useState<Case | null>(null)
  const [tab, setTab] = useState<'case' | 'questions' | 'chat'>('case')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submissionId, setSubmissionId] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [chat, setChat] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState('')
  const [agentTyping, setAgentTyping] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  const matrikel = typeof window !== 'undefined' ? sessionStorage.getItem('matrikelnummer') ?? '' : ''
  const userId   = typeof window !== 'undefined' ? sessionStorage.getItem('user_id') ?? '' : ''

  // Load case
  useEffect(() => {
    apiFetch<Case>(`/admin/cases/${id}`).then(setCase)
  }, [id])

  // Create submission + session on mount
  useEffect(() => {
    if (!id || !userId) return
    apiFetch<{ submission_id: string }>('/submissions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, matrikelnummer: matrikel, case_id: id, target_tp: 1 }),
    }).then(r => setSubmissionId(r.submission_id))

    apiFetch<{ session_id: string; websocket_url: string }>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, case_id: id }),
    }).then(r => {
      setSessionId(r.session_id)
      const wsBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/^http/, 'ws')
      const ws = new WebSocket(`${wsBase}/ws/${r.session_id}?case_id=${id}&user_id=${encodeURIComponent(userId)}`)
      ws.onopen = () => {
        console.log('WebSocket connected')
        setChat(c => c.length === 0 ? [{ role: 'agent', content: 'Hallo! Ich bin dein Lernbegleiter für diesen Case. Was beschäftigt dich — wo möchtest du anfangen?', agent_type: 'metacognitive' }] : c)
      }
      ws.onerror = e => console.error('WebSocket error', e)
      ws.onmessage = e => {
        const data = JSON.parse(e.data)
        if (data.event === 'agent_typing') { setAgentTyping(data.is_typing); return }
        if (data.event === 'agent_response') {
          setChat(c => [...c, { role: 'agent', content: data.content, agent_type: data.agent_type }])
        }
      }
      wsRef.current = ws
    })
    return () => wsRef.current?.close()
  }, [id, userId])

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [chat, agentTyping])

  const sendChat = () => {
    if (!chatInput.trim()) return
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not open, state:', wsRef.current?.readyState)
      return
    }
    setChat(c => [...c, { role: 'user', content: chatInput }])
    wsRef.current.send(JSON.stringify({ type: 'message', content: chatInput }))
    setChatInput('')
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
    await apiFetch(`/submissions/${submissionId}/submit`, { method: 'POST' })
    setSubmitted(true)
    router.push(`/results/${submissionId}`)
  }

  if (!caseData) return (
    <>
      <Nav />
      <main className="pt-32 px-8 text-sm" style={{ color: 'var(--muted)' }}>Wird geladen…</main>
    </>
  )

  const tabs = [
    { key: 'case',      label: 'Case lesen',   icon: <FileText size={14} /> },
    { key: 'questions', label: 'Fragen',        icon: <FileText size={14} /> },
    { key: 'chat',      label: 'Agent',         icon: <MessageSquare size={14} /> },
  ] as const

  return (
    <>
      <Nav />
      <main className="pt-24 pb-0 h-screen flex flex-col max-w-5xl mx-auto px-8">

        {/* Case header */}
        <div className="py-6">
          <p className="text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted)' }}>
            {caseData.industry} · {caseData.country}
          </p>
          <h1 className="font-display text-3xl leading-tight">{caseData.title}</h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--muted)' }}>{caseData.tagline}</p>
        </div>

        <div className="divider" />

        {/* Tabs */}
        <div className="flex gap-0 mt-0 border-b" style={{ borderColor: 'rgba(53,40,30,0.12)' }}>
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={clsx(
                'flex items-center gap-2 px-5 py-3 text-xs font-medium tracking-wide transition-all border-b-2 -mb-px',
                tab === t.key
                  ? 'border-[var(--accent)] text-[var(--accent)]'
                  : 'border-transparent hover:text-[var(--accent)]'
              )}
              style={{ color: tab === t.key ? 'var(--accent)' : 'var(--muted)' }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto py-8">

          {/* CASE TAB */}
          {tab === 'case' && (
            <div className="max-w-2xl flex flex-col gap-10">
              {caseData.sections.map(s => (
                <section key={s.section_id}>
                  <h2 className="font-medium mb-3 text-base">{s.title}</h2>
                  <p className="text-sm leading-7" style={{ color: 'var(--ink)' }}>{s.content}</p>
                </section>
              ))}
              {caseData.exhibits.length > 0 && (
                <section>
                  <h2 className="font-medium mb-5 text-base">Exhibits</h2>
                  <div className="flex flex-col gap-6">
                    {caseData.exhibits.map(ex => (
                      <div key={ex.exhibit_id} style={{ border: '1px solid rgba(53,40,30,0.15)', padding: '1.25rem' }}>
                        <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
                          {ex.title}
                        </p>
                        <pre className="text-xs leading-5 whitespace-pre-wrap" style={{ fontFamily: 'inherit' }}>
                          {ex.content}
                        </pre>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}

          {/* QUESTIONS TAB */}
          {tab === 'questions' && (
            <div className="max-w-2xl flex flex-col gap-8">
              {caseData.questions.map((q, i) => (
                <div key={q.question_id}>
                  <div className="flex items-start justify-between mb-3 gap-4">
                    <div className="flex items-start gap-4">
                      <span className="text-xs font-mono mt-0.5 shrink-0" style={{ color: 'var(--muted)' }}>
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <p className="text-sm leading-6">{q.text}</p>
                    </div>
                    <span
                      className="text-xs shrink-0 px-2 py-0.5"
                      style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                    >
                      {q.max_points} Pkt
                    </span>
                  </div>
                  <textarea
                    value={answers[q.question_id] ?? ''}
                    onChange={e => setAnswers(a => ({ ...a, [q.question_id]: e.target.value }))}
                    rows={5}
                    placeholder="Deine Antwort…"
                    className="w-full px-4 py-3 text-sm bg-transparent outline-none resize-none transition-all ml-8"
                    style={{ border: '1px solid rgba(53,40,30,0.2)', color: 'var(--ink)' }}
                    onFocus={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                    onBlur={e => { e.currentTarget.style.borderColor = 'rgba(53,40,30,0.2)'; saveAnswer(q.question_id, e.target.value) }}
                  />
                </div>
              ))}

              <div className="divider" />
              <button
                onClick={handleSubmit}
                disabled={submitted}
                className="self-start flex items-center gap-3 px-6 py-3 text-sm font-medium tracking-wide transition-all duration-200"
                style={{ background: 'var(--ink)', color: 'var(--white)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'var(--ink)')}
              >
                Abgeben & auswerten
              </button>
            </div>
          )}

          {/* CHAT TAB */}
          {tab === 'chat' && (
            <div className="flex flex-col h-full" style={{ minHeight: '60vh' }}>
              <div className="flex-1 flex flex-col gap-4 pb-4">
                {chat.length === 0 && (
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>
                    Stell dem Agenten eine Frage zu deiner Analyse — er gibt dir keine Antworten, sondern hilft dir, selbst zu denken.
                  </p>
                )}
                {chat.map((m, i) => (
                  <div key={i} className={clsx('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
                    {m.role === 'agent' && (
                      <span
                        className="text-xs mr-2 mt-2 shrink-0 font-medium"
                        style={{ color: 'var(--accent)' }}
                      >
                        {AGENT_LABEL[m.agent_type ?? ''] ?? 'Agent'}
                      </span>
                    )}
                    <div
                      className="max-w-md px-4 py-3 text-sm leading-6"
                      style={m.role === 'user'
                        ? { background: 'var(--ink)', color: 'var(--white)' }
                        : { background: 'var(--surface)', color: 'var(--ink)', border: '1px solid rgba(53,40,30,0.12)' }
                      }
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
                {agentTyping && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs" style={{ color: 'var(--accent)' }}>Agent</span>
                    <span className="text-xs" style={{ color: 'var(--muted)' }}>schreibt…</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Chat input */}
              <div
                className="sticky bottom-0 flex gap-0 pb-4 pt-2"
                style={{ background: 'var(--bg)' }}
              >
                <input
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendChat())}
                  placeholder="Frag den Agenten…"
                  className="flex-1 px-4 py-3 text-sm bg-transparent outline-none"
                  style={{ border: '1px solid rgba(53,40,30,0.2)', borderRight: 'none', color: 'var(--ink)' }}
                  onFocus={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                  onBlur={e => e.currentTarget.style.borderColor = 'rgba(53,40,30,0.2)'}
                />
                <button
                  onClick={sendChat}
                  className="px-4 py-3 transition-all duration-150"
                  style={{ background: 'var(--ink)', color: 'var(--white)' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'var(--ink)')}
                >
                  <Send size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </>
  )
}
