'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowRight, BookOpen, LayoutDashboard, ShieldCheck } from 'lucide-react'

interface LoginPageContentProps {
  prolificPid?: string
  studyId?: string
  prolificSessionId?: string
  initialMode?: AppMode
  teacherLoginError?: boolean
}

const EXPERIMENT_NAME = 'prolific_experimental_run'
type AppMode = 'student' | 'teacher'

function LoginPageContent({
  prolificPid = '',
  studyId = '',
  prolificSessionId = '',
  initialMode = 'student',
  teacherLoginError = false,
}: LoginPageContentProps) {
  const router = useRouter()
  const [mode, setMode] = useState<AppMode>(() => {
    if (typeof window === 'undefined') return 'student'
    if (prolificPid) return 'student'
    if (initialMode === 'teacher') return 'teacher'
    return sessionStorage.getItem('app_mode') === 'teacher' ? 'teacher' : 'student'
  })
  const [participantIdInput, setParticipantIdInput] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const resolvedParticipantId = participantIdInput.trim() || prolificPid.trim()

  useEffect(() => {
    if (typeof window === 'undefined') return

    if (prolificPid) {
      setMode('student')
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
    }))

    if (prolificPid) {
      setParticipantIdInput(current => current || prolificPid)
      sessionStorage.setItem('matrikelnummer', prolificPid)
      sessionStorage.setItem('user_id', `prolific_${prolificPid}`)
    }
  }, [mode, prolificPid, prolificSessionId, resolvedParticipantId, studyId])

  const switchMode = (nextMode: AppMode) => {
    setMode(nextMode)
    setError('')
    sessionStorage.setItem('app_mode', nextMode)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const participantId = resolvedParticipantId
    if (!participantId) {
      setError('Bitte Prolific-ID eingeben.')
      return
    }
    setLoading(true)

    sessionStorage.setItem('experiment_context', JSON.stringify({
      provider: 'prolific',
      experiment_name: EXPERIMENT_NAME,
      run_id: prolificSessionId || participantId,
      prolific_pid: participantId,
      prolific_study_id: studyId || undefined,
      prolific_session_id: prolificSessionId || undefined,
    }))

    sessionStorage.setItem('matrikelnummer', participantId)
    sessionStorage.setItem('user_id', `prolific_${participantId}`)
    router.push('/cases')
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6">
      <div className="mb-20 text-center select-none">
        <h1
          className="font-display leading-none tracking-tight"
          style={{ fontSize: 'clamp(4rem, 14vw, 11rem)', color: 'var(--ink)' }}
        >
          ToAdapt
        </h1>
        <p className="mt-3 text-sm tracking-[0.2em] uppercase" style={{ color: 'var(--muted)' }}>
          {mode === 'student' ? 'Tansfer-Learning mit Business Cases' : 'Lehrkräftebereich'}
        </p>
      </div>

      {!prolificPid && (
        <div
          className="mb-8 flex w-full max-w-sm items-center gap-1 p-1"
          style={{ border: '1px solid rgba(53,40,30,0.16)', background: 'rgba(250,250,248,0.45)' }}
          aria-label="Modus wählen"
        >
          {[
            { id: 'student' as const, label: 'Studierende' },
            { id: 'teacher' as const, label: 'Lehrkräfte' },
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
              Anmeldung
            </p>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <label className="block text-xs mb-2 font-medium tracking-wide" style={{ color: 'var(--line)' }}>
                  Matrikelnummer
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
                  Mit dem Absenden bestätigst du, dass deine Antwort eigenständig verfasst ist. Mit ChatGPT oder
                  anderen KI-Tools generierte Antworten werden mit GPTZero überprüft und führen zum Ausschluss der Auszahlung.
                </p>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="group flex items-center justify-between px-5 py-3 text-sm font-medium tracking-wide transition-all duration-200"
                style={{ background: 'var(--ink)', color: 'var(--white)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'var(--ink)')}
              >
                {loading ? 'Wird geladen…' : 'Weiter'}
                <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-1" />
              </button>
            </form>
          </>
        ) : (
          <form action="/teacher-login" method="post" className="flex flex-col gap-4">
            <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
              Lehrkräfte
            </p>
            <div>
              <label className="block text-xs mb-2 font-medium tracking-wide" style={{ color: 'var(--line)' }}>
                Zugangscode
              </label>
              <input
                type="password"
                inputMode="numeric"
                name="teacher_code"
                placeholder="Code eingeben"
                className="w-full px-4 py-3 text-sm bg-transparent outline-none transition-all"
                style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
                onFocus={event => { event.currentTarget.style.borderColor = 'var(--accent)' }}
                onBlur={event => { event.currentTarget.style.borderColor = 'rgba(53,40,30,0.25)' }}
              />
              {teacherLoginError && <p className="mt-2 text-xs" style={{ color: '#c0392b' }}>Code nicht korrekt.</p>}
            </div>

            <button
              type="submit"
              className="group flex items-center justify-between px-5 py-3 text-sm font-medium tracking-wide transition-all duration-200"
              style={{ background: 'var(--ink)', color: 'var(--white)' }}
              onMouseEnter={event => { event.currentTarget.style.background = 'var(--accent)' }}
              onMouseLeave={event => { event.currentTarget.style.background = 'var(--ink)' }}
            >
              Lehrkräftebereich öffnen
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
          Deine Matrikelnummer wird für die Studienzuordnung erfasst. Chat-Logs bleiben aus dem Dozierenden-Dashboard ausgeschlossen.
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
