'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight } from 'lucide-react'

export default function LoginPage() {
  const router = useRouter()
  const [matrikel, setMatrikel] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!matrikel.trim()) { setError('Bitte Matrikelnummer eingeben.'); return }
    setLoading(true)
    sessionStorage.setItem('matrikelnummer', matrikel.trim())
    sessionStorage.setItem('user_id', `u_${matrikel.trim()}`)
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
              Matrikelnummer
            </label>
            <input
              type="text"
              value={matrikel}
              onChange={e => { setMatrikel(e.target.value); setError('') }}
              placeholder="12-345-678"
              autoFocus
              className="w-full px-4 py-3 text-sm bg-transparent outline-none transition-all"
              style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
              onFocus={e => e.currentTarget.style.borderColor = 'var(--accent)'}
              onBlur={e => e.currentTarget.style.borderColor = 'rgba(53,40,30,0.25)'}
            />
            {error && <p className="mt-2 text-xs" style={{ color: '#c0392b' }}>{error}</p>}
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
        Deine Antworten werden anonym ausgewertet. Keine Chat-Logs werden an Dozierende weitergegeben.
      </p>
    </main>
  )
}
