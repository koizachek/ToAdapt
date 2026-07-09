'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowRight, BookOpen, LayoutDashboard, ShieldCheck, X } from 'lucide-react'
import NotionIcon from '@/components/NotionIcon'
import { languageFromSearchParams, Locale } from '@/lib/i18n'
import { useLanguage } from '@/lib/useLanguage'

interface LoginPageContentProps {
  prolificPid?: string
  studyId?: string
  prolificSessionId?: string
  initialMode?: AppMode
  teacherLoginError?: boolean
  initialLanguage?: Locale | null
}

const EXPERIMENT_NAME = 'prolific_experimental_run'   // nur bei Prolific-URL-Ankunft
const COURSE_CONTEXT_NAME = 'toadapt_course'          // regulärer Kursbetrieb
type AppMode = 'student' | 'teacher'

const LOGIN_TEXT = {
  de: {
    taglineStudent: 'Kompetenzentwicklung mit Business Cases',
    taglineTeacher: 'Lehrkräftebereich',
    modeAria: 'Modus wählen',
    studentMode: 'Studierende',
    teacherMode: 'Lehrkräfte',
    studentSection: 'Anmeldung',
    participantLabel: 'Teilnehmer-ID',
    participantMissing: 'Bitte Teilnehmer-ID eingeben.',
    groupLabel: 'Gruppen-Nr. oder Gruppencode',
    groupPlaceholder: 'z.B. 12 oder G12',
    groupMissing: 'Bitte Gruppen-Nr. eingeben — dein Tutor-Team hat sie euch mitgeteilt.',
    studentAccessCode: 'Zugangscode (falls von der Lehrperson ausgegeben)',
    studentAccessError: 'Zugangscode fehlt oder ist nicht korrekt.',
    loginUnavailable: 'Anmeldung derzeit nicht möglich — bitte später erneut versuchen.',
    integrityNote: 'Mit dem Absenden bestätigst du, dass deine Antworten eigenständig verfasst sind. To:Adapt unterstützt dein Denken — es ersetzt es nicht.',
    loading: 'Wird geladen...',
    continue: 'Weiter',
    teacherSection: 'Lehrkräfte',
    accessCode: 'Zugangscode',
    accessPlaceholder: 'Code eingeben',
    accessError: 'Code nicht korrekt.',
    openTeacher: 'Lehrkräftebereich öffnen',
    privacyNote: 'Deine Angaben werden pseudonymisiert erfasst. Tutor:innen sehen nur Gruppen-Zusammenfassungen — keine Einzelprofile und keine Chat-Verläufe.',
    languageAria: 'Sprache wählen',
    aboutToggle: 'Über To:Adapt',
    imprint: 'Impressum',
    aboutClose: 'Einklappen',
    aboutWhatTitle: 'Was ist To:Adapt?',
    aboutWhat: 'To:Adapt ist eine Lernumgebung zur Kompetenzentwicklung mit Business Cases. Du bearbeitest realistische Fälle eigenständig — ein KI-Lernbegleiter unterstützt dein Denken mit Rückfragen und Hinweisen, gibt aber bewusst keine Lösungen vor. Deine Abgaben erhalten automatisches, formatives Feedback. Tutor:innen sehen ausschließlich Zusammenfassungen deiner Übungsgruppe, niemals Einzelprofile oder Chat-Verläufe.',
    aboutHowTitle: 'So funktioniert es',
    aboutSteps: [
      'Melde dich mit deiner Teilnehmer-ID und deiner Gruppen-Nr. an (bekommst du von deinem Tutor-Team).',
      'Lies den Case. Markierte Fachbegriffe kannst du anklicken — sie starten eine Erklärung im Lernchat.',
      'Denke mit dem Lernbegleiter: Er stellt Fragen und zeigt Denkrichtungen, statt Antworten zu liefern.',
      'Beantworte die Fragen in ganzen Sätzen. Die Canvas-Anzeige, der Selbst-Check und bis zu zwei Denkanstöße pro Frage helfen dir, Lücken selbst zu finden.',
      'Gib ab und sieh dir dein Feedback an — es zeigt Stärken und offene Denkschritte, keine Musterlösung.',
    ],
  },
  en: {
    taglineStudent: 'Competency development with business cases',
    taglineTeacher: 'Teacher area',
    modeAria: 'Choose mode',
    studentMode: 'Students',
    teacherMode: 'Teachers',
    studentSection: 'Login',
    participantLabel: 'Participant ID',
    participantMissing: 'Please enter your participant ID.',
    groupLabel: 'Group number or group code',
    groupPlaceholder: 'e.g. 12 or G12',
    groupMissing: 'Please enter your group number — your tutor team shared it with you.',
    studentAccessCode: 'Access code (if provided by your teacher)',
    studentAccessError: 'Access code is missing or incorrect.',
    loginUnavailable: 'Login is currently unavailable — please try again later.',
    integrityNote: 'By submitting, you confirm that your answers are your own work. To:Adapt supports your thinking — it does not replace it.',
    loading: 'Loading...',
    continue: 'Continue',
    teacherSection: 'Teachers',
    accessCode: 'Access code',
    accessPlaceholder: 'Enter code',
    accessError: 'Incorrect code.',
    openTeacher: 'Open teacher area',
    privacyNote: 'Your data is stored pseudonymously. Tutors only see group summaries — no individual profiles and no chat logs.',
    languageAria: 'Choose language',
    aboutToggle: 'About To:Adapt',
    imprint: 'Legal notice',
    aboutClose: 'Collapse',
    aboutWhatTitle: 'What is To:Adapt?',
    aboutWhat: 'To:Adapt is a learning environment for competency development with business cases. You work through realistic cases on your own — an AI learning companion supports your thinking with questions and hints, but deliberately never gives away solutions. Your submissions receive automatic, formative feedback. Tutors only ever see summaries of your tutorial group, never individual profiles or chat logs.',
    aboutHowTitle: 'How it works',
    aboutSteps: [
      'Log in with your participant ID and your group number (provided by your tutor team).',
      'Read the case. Highlighted terms are clickable — they start an explanation in the learning chat.',
      'Think with the learning companion: it asks questions and points out directions instead of delivering answers.',
      'Answer the questions in complete sentences. The canvas indicator, the self-check, and up to two thinking prompts per question help you find gaps yourself.',
      'Submit and review your feedback — it shows strengths and open thinking steps, not a model solution.',
    ],
  },
} satisfies Record<Locale, Record<string, string | string[]>>

function LoginPageContent({
  prolificPid = '',
  studyId = '',
  prolificSessionId = '',
  initialMode = 'student',
  teacherLoginError = false,
  initialLanguage = null,
}: LoginPageContentProps) {
  const router = useRouter()
  const [language, setLanguage] = useLanguage()
  const [mode, setMode] = useState<AppMode>(() => {
    if (typeof window === 'undefined') return 'student'
    if (prolificPid) return 'student'
    if (initialMode === 'teacher') return 'teacher'
    return sessionStorage.getItem('app_mode') === 'teacher' ? 'teacher' : 'student'
  })
  const [participantIdInput, setParticipantIdInput] = useState(prolificPid)
  const [groupCodeInput, setGroupCodeInput] = useState(() => {
    if (typeof window === 'undefined') return ''
    return sessionStorage.getItem('group_code') ?? ''
  })
  const [accessCodeInput, setAccessCodeInput] = useState(() => {
    if (typeof window === 'undefined') return ''
    return sessionStorage.getItem('student_access_code') ?? ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showAbout, setShowAbout] = useState(false)

  useEffect(() => {
    if (!showAbout) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setShowAbout(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [showAbout])

  const resolvedParticipantId = participantIdInput.trim() || prolificPid.trim()
  const text = LOGIN_TEXT[language]

  useEffect(() => {
    if (initialLanguage && initialLanguage !== language) {
      setLanguage(initialLanguage)
    }
  }, [initialLanguage, language, setLanguage])

  useEffect(() => {
    if (typeof window === 'undefined') return

    if (prolificPid) {
      sessionStorage.setItem('app_mode', 'student')
    }
    if (mode === 'teacher') {
      sessionStorage.setItem('app_mode', 'teacher')
      return
    }

    sessionStorage.setItem('app_mode', 'student')
    // Prolific-Kontext nur bei echter Prolific-Ankunft (URL-Parameter) —
    // regulärer Kursbetrieb läuft neutral als To:Adapt.
    const isProlificArrival = Boolean(prolificPid || studyId || prolificSessionId)
    sessionStorage.setItem('experiment_context', JSON.stringify({
      provider: isProlificArrival ? 'prolific' : undefined,
      experiment_name: isProlificArrival ? EXPERIMENT_NAME : COURSE_CONTEXT_NAME,
      run_id: prolificSessionId || undefined,
      prolific_pid: isProlificArrival ? (resolvedParticipantId || undefined) : undefined,
      prolific_study_id: studyId || undefined,
      prolific_session_id: prolificSessionId || undefined,
      metadata: { language },
    }))

    if (prolificPid) {
      sessionStorage.setItem('matrikelnummer', prolificPid)
      sessionStorage.setItem('user_id', `prolific_${prolificPid}`)
    }
  }, [language, mode, prolificPid, prolificSessionId, resolvedParticipantId, studyId])

  const switchMode = (nextMode: AppMode) => {
    setMode(nextMode)
    setError('')
    sessionStorage.setItem('app_mode', nextMode)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const participantId = resolvedParticipantId
    if (!participantId) {
      setError(text.participantMissing)
      return
    }
    // Gruppen-Selbstauskunft: Pflicht im Kursbetrieb; Prolific-Läufe
    // (PROLIFIC_PID in der URL) kennen keine Gruppen.
    const groupCode = groupCodeInput.trim()
    if (!prolificPid && !groupCode) {
      setError(text.groupMissing)
      return
    }
    setLoading(true)
    if (groupCode) {
      sessionStorage.setItem('group_code', groupCode)
    } else {
      sessionStorage.removeItem('group_code')
    }

    // Zugangscode speichern und gegen das Backend prüfen (401 = falsch/fehlt;
    // ist serverseitig kein Code konfiguriert, geht der Check immer durch).
    const trimmedCode = accessCodeInput.trim()
    if (trimmedCode) {
      sessionStorage.setItem('student_access_code', trimmedCode)
    } else {
      sessionStorage.removeItem('student_access_code')
    }
    try {
      const { apiFetch } = await import('@/lib/api')
      await apiFetch('/auth/student/verify', { method: 'POST' })
    } catch (err) {
      setLoading(false)
      // Technischen Grund in die Browser-Konsole (Diagnose: falsche
      // NEXT_PUBLIC_API_URL, CORS oder Backend nicht erreichbar).
      console.error('Login-Verify fehlgeschlagen:', err)
      const message = err instanceof Error ? err.message : ''
      setError(/zugangscode|access code/i.test(message) ? text.studentAccessError : text.loginUnavailable)
      return
    }

    const isProlificArrival = Boolean(prolificPid || studyId || prolificSessionId)
    sessionStorage.setItem('experiment_context', JSON.stringify({
      provider: isProlificArrival ? 'prolific' : undefined,
      experiment_name: isProlificArrival ? EXPERIMENT_NAME : COURSE_CONTEXT_NAME,
      run_id: prolificSessionId || undefined,
      prolific_pid: isProlificArrival ? participantId : undefined,
      prolific_study_id: studyId || undefined,
      prolific_session_id: prolificSessionId || undefined,
      metadata: { language, ...(groupCode ? { group_code: groupCode } : {}) },
    }))

    sessionStorage.setItem('matrikelnummer', participantId)
    sessionStorage.setItem('user_id', isProlificArrival ? `prolific_${participantId}` : `p_${participantId}`)
    router.push('/cases')
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <div
        className="fixed right-6 top-6 flex items-center gap-1 p-1"
        style={{ border: '1px solid var(--hairline)', background: 'rgba(250,250,248,0.45)' }}
        aria-label={text.languageAria}
      >
        {(['de', 'en'] as Locale[]).map(option => {
          const active = language === option
          return (
            <button
              key={option}
              type="button"
              onClick={() => setLanguage(option)}
              className="px-2.5 py-1.5 text-xs font-medium tracking-widest transition-colors"
              style={{
                background: active ? 'var(--ink)' : 'transparent',
                color: active ? 'var(--white)' : 'var(--ink)',
              }}
              aria-pressed={active}
            >
              {option.toUpperCase()}
            </button>
          )
        })}
      </div>

      <div className="mb-20 text-center select-none">
        <h1
          className="font-display leading-none tracking-tight"
          style={{ fontSize: 'clamp(3.2rem, 13vw, 10.2rem)', color: 'var(--ink)' }}
        >
          ToAdapt
        </h1>
        <p className="mt-3 text-sm tracking-[0.2em] uppercase" style={{ color: 'var(--muted)' }}>
          {mode === 'student' ? text.taglineStudent : text.taglineTeacher}
        </p>
        <button
          type="button"
          onClick={() => setShowAbout(true)}
          aria-haspopup="dialog"
          className="mx-auto mt-5 flex items-center gap-2.5 px-4 py-2 text-xs font-medium tracking-wide transition-colors hover:opacity-80"
          style={{ color: 'var(--muted)' }}
        >
          <NotionIcon name="compass" size={26} />
          {text.aboutToggle}
        </button>
      </div>

      {!prolificPid && (
        <div
          className="mb-8 flex w-full max-w-sm items-center gap-1 p-1"
          style={{ border: '1px solid var(--hairline)', background: 'rgba(250,250,248,0.45)' }}
          aria-label={text.modeAria}
        >
          {[
            { id: 'student' as const, label: text.studentMode },
            { id: 'teacher' as const, label: text.teacherMode },
          ].map(option => {
            const active = mode === option.id
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => switchMode(option.id)}
                className="flex-1 px-4 py-2 text-sm font-medium transition-colors"
                style={{
                  background: active ? 'var(--ink)' : 'transparent',
                  color: active ? 'var(--white)' : 'var(--ink)',
                }}
                aria-pressed={active}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      )}

      <div
        className="w-full max-w-sm p-8"
        style={{ background: 'var(--surface)', border: '1px solid var(--hairline)' }}
      >
        {mode === 'student' ? (
          <>
            <p className="text-xs tracking-widest uppercase mb-6" style={{ color: 'var(--muted)' }}>
              {text.studentSection}
            </p>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <label className="block text-xs mb-2 font-medium tracking-wide" style={{ color: 'var(--line)' }}>
                  {text.participantLabel}
                </label>
                <input
                  type="text"
                  value={participantIdInput}
                  onChange={e => { setParticipantIdInput(e.target.value); setError('') }}
                  placeholder="deine-id"
                  autoFocus
                  className="w-full px-4 py-3 text-sm bg-transparent outline-none transition-all"
                  style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
                  onFocus={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                  onBlur={e => e.currentTarget.style.borderColor = 'rgba(53,40,30,0.25)'}
                />
                {error && <p className="mt-2 text-xs" style={{ color: '#c0392b' }}>{error}</p>}
                <p className="mt-2 text-xs leading-5" style={{ color: '#ad3f2b' }}>
                  {text.integrityNote}
                </p>
              </div>

              {!prolificPid && (
                <div>
                  <label className="block text-xs mb-2 font-medium tracking-wide" style={{ color: 'var(--line)' }}>
                    {text.groupLabel}
                  </label>
                  <input
                    type="text"
                    value={groupCodeInput}
                    onChange={e => { setGroupCodeInput(e.target.value); setError('') }}
                    placeholder={text.groupPlaceholder}
                    className="w-full px-4 py-3 text-sm bg-transparent outline-none transition-all"
                    style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
                    onFocus={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                    onBlur={e => e.currentTarget.style.borderColor = 'rgba(53,40,30,0.25)'}
                  />
                </div>
              )}

              <div>
                <label className="block text-xs mb-2 font-medium tracking-wide" style={{ color: 'var(--line)' }}>
                  {text.studentAccessCode}
                </label>
                <input
                  type="password"
                  value={accessCodeInput}
                  onChange={e => { setAccessCodeInput(e.target.value); setError('') }}
                  placeholder={text.accessPlaceholder}
                  className="w-full px-4 py-3 text-sm bg-transparent outline-none transition-all"
                  style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
                  onFocus={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                  onBlur={e => e.currentTarget.style.borderColor = 'rgba(53,40,30,0.25)'}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="group flex items-center justify-between px-5 py-3 text-sm font-medium tracking-wide transition-all duration-200"
                style={{ background: 'var(--ink)', color: 'var(--white)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'var(--ink)')}
              >
                {loading ? text.loading : text.continue}
                <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-1" />
              </button>
            </form>
          </>
        ) : (
          <form action="/teacher-login" method="post" className="flex flex-col gap-4">
            <input type="hidden" name="language" value={language} />
            <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
              {text.teacherSection}
            </p>
            <div>
              <label className="block text-xs mb-2 font-medium tracking-wide" style={{ color: 'var(--line)' }}>
                {text.accessCode}
              </label>
              <input
                type="password"
                inputMode="numeric"
                name="teacher_code"
                placeholder={text.accessPlaceholder}
                className="w-full px-4 py-3 text-sm bg-transparent outline-none transition-all"
                style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
                onFocus={event => { event.currentTarget.style.borderColor = 'var(--accent)' }}
                onBlur={event => { event.currentTarget.style.borderColor = 'rgba(53,40,30,0.25)' }}
              />
              {teacherLoginError && <p className="mt-2 text-xs" style={{ color: '#c0392b' }}>{text.accessError}</p>}
            </div>

            <button
              type="submit"
              className="group flex items-center justify-between px-5 py-3 text-sm font-medium tracking-wide transition-all duration-200"
              style={{ background: 'var(--ink)', color: 'var(--white)' }}
              onMouseEnter={event => { event.currentTarget.style.background = 'var(--accent)' }}
              onMouseLeave={event => { event.currentTarget.style.background = 'var(--ink)' }}
            >
              {text.openTeacher}
              <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-1" />
            </button>

            <div className="grid grid-cols-3 gap-2 pt-2 text-xs" style={{ color: 'var(--muted)' }}>
              <span className="flex items-center gap-1"><BookOpen size={12} /> Cases</span>
              <span className="flex items-center gap-1"><LayoutDashboard size={12} /> Dashboard</span>
              <span className="flex items-center gap-1"><ShieldCheck size={12} /> Admin</span>
            </div>
          </form>
        )}
      </div>

      {mode === 'student' && (
        <p className="mt-10 text-xs text-center max-w-xs" style={{ color: 'var(--muted)' }}>
          {text.privacyNote}
        </p>
      )}

      {/* Impressum (Institutsseite) */}
      <a
        href="https://iwi.unisg.ch/en/the-institute/"
        target="_blank"
        rel="noopener noreferrer"
        className="mt-10 text-xs underline-offset-2 hover:underline"
        style={{ color: 'var(--muted)' }}
      >
        {text.imprint}
      </a>

      {showAbout && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={text.aboutToggle}
          className="fixed inset-0 z-40 flex items-center justify-center px-4 py-8"
          style={{ background: 'rgba(30,22,15,0.45)' }}
          onClick={() => setShowAbout(false)}
        >
          <div
            className="flex max-h-[85vh] w-full max-w-xl flex-col gap-6 overflow-y-auto rounded-2xl p-8 shadow-lg"
            style={{ background: 'var(--surface)', border: '1px solid var(--hairline)' }}
            onClick={event => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <h2 className="flex items-center gap-3 font-display text-2xl leading-tight">
                <NotionIcon name="compass" size={34} />
                To:Adapt
              </h2>
              <button
                type="button"
                onClick={() => setShowAbout(false)}
                aria-label={text.aboutClose}
                className="shrink-0 p-1.5 transition-colors hover:opacity-70"
                style={{ color: 'var(--muted)' }}
              >
                <X size={18} />
              </button>
            </div>

            <div>
              <h3 className="mb-2 flex items-center gap-2.5 text-sm font-medium">
                <NotionIcon name="idea" size={29} />
                {text.aboutWhatTitle}
              </h3>
              <p className="text-sm leading-6" style={{ color: 'var(--ink)' }}>
                {text.aboutWhat}
              </p>
            </div>

            <div>
              <h3 className="mb-3 flex items-center gap-2.5 text-sm font-medium">
                <NotionIcon name="questions" size={29} />
                {text.aboutHowTitle}
              </h3>
              <ol className="flex flex-col gap-2">
                {text.aboutSteps.map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm leading-6">
                    <span className="shrink-0 font-mono text-xs mt-0.5" style={{ color: 'var(--accent)' }}>
                      {i + 1}.
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

function LoginPageInner() {
  const searchParams = useSearchParams()

  return (
    <LoginPageContent
      prolificPid={searchParams.get('PROLIFIC_PID') ?? searchParams.get('prolific_pid') ?? ''}
      studyId={searchParams.get('STUDY_ID') ?? searchParams.get('study_id') ?? ''}
      prolificSessionId={searchParams.get('SESSION_ID') ?? searchParams.get('session_id') ?? ''}
      initialMode={searchParams.get('mode') === 'teacher' ? 'teacher' : 'student'}
      teacherLoginError={searchParams.get('teacher_error') === '1'}
      initialLanguage={languageFromSearchParams(new URLSearchParams(searchParams.toString()))}
    />
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageContent />}>
      <LoginPageInner />
    </Suspense>
  )
}
