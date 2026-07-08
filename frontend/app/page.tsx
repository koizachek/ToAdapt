'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowRight, BookOpen, LayoutDashboard, ShieldCheck } from 'lucide-react'
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

const EXPERIMENT_NAME = 'prolific_experimental_run'
type AppMode = 'student' | 'teacher'

const LOGIN_TEXT = {
  de: {
    taglineStudent: 'Transfer-Learning mit Business Cases',
    taglineTeacher: 'Lehrkräftebereich',
    modeAria: 'Modus wählen',
    studentMode: 'Studierende',
    teacherMode: 'Lehrkräfte',
    studentSection: 'Anmeldung',
    participantLabel: 'Matrikelnummer',
    participantMissing: 'Bitte Prolific-ID eingeben.',
    studentAccessCode: 'Zugangscode (falls von der Lehrperson ausgegeben)',
    studentAccessError: 'Zugangscode fehlt oder ist nicht korrekt.',
    loginUnavailable: 'Anmeldung derzeit nicht möglich — bitte später erneut versuchen.',
    integrityNote: 'Mit dem Absenden bestätigst du, dass deine Antwort eigenständig verfasst ist. Mit ChatGPT oder anderen KI-Tools generierte Antworten werden mit GPTZero überprüft.',
    loading: 'Wird geladen...',
    continue: 'Weiter',
    teacherSection: 'Lehrkräfte',
    accessCode: 'Zugangscode',
    accessPlaceholder: 'Code eingeben',
    accessError: 'Code nicht korrekt.',
    openTeacher: 'Lehrkräftebereich öffnen',
    privacyNote: 'Deine Matrikelnummer wird für die Studienzuordnung erfasst. Chat-Logs bleiben aus dem Dozierenden-Dashboard ausgeschlossen.',
    languageAria: 'Sprache wählen',
  },
  en: {
    taglineStudent: 'Transfer learning with business cases',
    taglineTeacher: 'Teacher area',
    modeAria: 'Choose mode',
    studentMode: 'Students',
    teacherMode: 'Teachers',
    studentSection: 'Login',
    participantLabel: 'Participant ID',
    participantMissing: 'Please enter your Prolific ID.',
    studentAccessCode: 'Access code (if provided by your teacher)',
    studentAccessError: 'Access code is missing or incorrect.',
    loginUnavailable: 'Login is currently unavailable — please try again later.',
    integrityNote: 'By submitting, you confirm that your answer is your own work. Answers generated with ChatGPT or other AI tools will be checked with GPTZero.',
    loading: 'Loading...',
    continue: 'Continue',
    teacherSection: 'Teachers',
    accessCode: 'Access code',
    accessPlaceholder: 'Enter code',
    accessError: 'Incorrect code.',
    openTeacher: 'Open teacher area',
    privacyNote: 'Your participant ID is stored for study assignment. Chat logs remain excluded from the teacher dashboard.',
    languageAria: 'Choose language',
  },
} satisfies Record<Locale, Record<string, string>>

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
  const [accessCodeInput, setAccessCodeInput] = useState(() => {
    if (typeof window === 'undefined') return ''
    return sessionStorage.getItem('student_access_code') ?? ''
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
    sessionStorage.setItem('experiment_context', JSON.stringify({
      provider: 'prolific',
      experiment_name: EXPERIMENT_NAME,
      run_id: prolificSessionId || resolvedParticipantId || undefined,
      prolific_pid: resolvedParticipantId || undefined,
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
    setLoading(true)

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
      const message = err instanceof Error ? err.message : ''
      setError(/zugangscode|access code/i.test(message) ? text.studentAccessError : text.loginUnavailable)
      return
    }

    sessionStorage.setItem('experiment_context', JSON.stringify({
      provider: 'prolific',
      experiment_name: EXPERIMENT_NAME,
      run_id: prolificSessionId || participantId,
      prolific_pid: participantId,
      prolific_study_id: studyId || undefined,
      prolific_session_id: prolificSessionId || undefined,
      metadata: { language },
    }))

    sessionStorage.setItem('matrikelnummer', participantId)
    sessionStorage.setItem('user_id', `prolific_${participantId}`)
    router.push('/cases')
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <div
        className="fixed right-6 top-6 flex items-center gap-1 p-1"
        style={{ border: '1px solid rgba(53,40,30,0.16)', background: 'rgba(250,250,248,0.45)' }}
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
          style={{ fontSize: 'clamp(4rem, 14vw, 11rem)', color: 'var(--ink)' }}
        >
          ToAdapt
        </h1>
        <p className="mt-3 text-sm tracking-[0.2em] uppercase" style={{ color: 'var(--muted)' }}>
          {mode === 'student' ? text.taglineStudent : text.taglineTeacher}
        </p>
      </div>

      {!prolificPid && (
        <div
          className="mb-8 flex w-full max-w-sm items-center gap-1 p-1"
          style={{ border: '1px solid rgba(53,40,30,0.16)', background: 'rgba(250,250,248,0.45)' }}
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
        style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.15)' }}
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
                  placeholder="5f7c2e4a9b1c..."
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
