'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowRight } from 'lucide-react'

interface LoginPageContentProps {
  prolificPid?: string
  studyId?: string
  prolificSessionId?: string
}

const EXPERIMENT_NAME = 'prolific_experimental_run'

function LoginPageContent({
  prolificPid = '',
  studyId = '',
  prolificSessionId = '',
}: LoginPageContentProps) {
  const router = useRouter()
  const [participantIdInput, setParticipantIdInput] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const resolvedParticipantId = participantIdInput.trim() || prolificPid.trim()

  useEffect(() => {
    if (typeof window === 'undefined') return

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
  }, [prolificPid, prolificSessionId, resolvedParticipantId, studyId])

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
          Transfer-Trainer · BWL A · Universität St. Gallen
        </p>
      </div>

      <div
        className="w-full max-w-sm p-8"
        style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.15)' }}
      >
        <p className="text-xs tracking-widest uppercase mb-6" style={{ color: 'var(--muted)' }}>
          Anmeldung
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block text-xs mb-2 font-medium tracking-wide" style={{ color: 'var(--line)' }}>
              Prolific-ID
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
      </div>

      <p className="mt-10 text-xs text-center max-w-xs" style={{ color: 'var(--muted)' }}>
        Deine Prolific-ID wird für die Studienzuordnung erfasst. Chat-Logs bleiben aus dem Dozierenden-Dashboard ausgeschlossen.
      </p>
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
