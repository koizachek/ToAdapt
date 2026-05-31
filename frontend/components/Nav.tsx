'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import clsx from 'clsx'
import { useState } from 'react'
import { GraduationCap, UserRoundCog } from 'lucide-react'

type AppMode = 'student' | 'teacher'

const studentLinks = [
  { href: '/cases', label: 'Cases' },
]

const teacherLinks = [
  { href: '/cases', label: 'Cases' },
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/admin', label: 'Admin' },
]

function modeFromPath(path: string): AppMode | null {
  if (path.startsWith('/dashboard') || path.startsWith('/admin')) return 'teacher'
  if (path.startsWith('/results') || path.startsWith('/goodbye')) return 'student'
  return null
}

export default function Nav() {
  const path = usePathname()
  const router = useRouter()
  const [selectedMode, setSelectedMode] = useState<AppMode>(() => {
    if (typeof window === 'undefined') return 'student'
    try {
      const storedMode = sessionStorage.getItem('app_mode') as AppMode | null
      return storedMode === 'teacher' ? 'teacher' : 'student'
    } catch {
      return 'student'
    }
  })
  const [isExperimentalRun] = useState(() => {
    if (typeof window === 'undefined') return false
    try {
      const experimentContext = JSON.parse(sessionStorage.getItem('experiment_context') ?? 'null')
      return experimentContext?.provider === 'prolific'
    } catch {
      return false
    }
  })
  const mode = isExperimentalRun ? 'student' : modeFromPath(path) ?? selectedMode

  const visibleLinks = isExperimentalRun || mode === 'student'
    ? studentLinks
    : teacherLinks

  const switchMode = (nextMode: AppMode) => {
    sessionStorage.setItem('app_mode', nextMode)
    setSelectedMode(nextMode)
    router.push(nextMode === 'teacher' ? '/dashboard' : '/cases')
  }

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between gap-6 px-8 py-5"
      style={{ borderBottom: '1px solid rgba(53,40,30,0.12)', background: 'rgba(223,221,214,0.92)', backdropFilter: 'blur(12px)' }}
    >
      {/* Wordmark */}
      <Link href="/" className="font-display text-xl tracking-tight" style={{ color: 'var(--ink)' }}>
        ToAdapt
      </Link>

      {/* Nav links */}
      <nav className="flex items-center gap-8">
        {!isExperimentalRun && (
          <div
            className="flex items-center gap-1 p-1"
            style={{ border: '1px solid rgba(53,40,30,0.16)', background: 'rgba(250,250,248,0.45)' }}
            aria-label="Modus wählen"
          >
            {[
              { id: 'student' as const, label: 'Studierende', icon: GraduationCap },
              { id: 'teacher' as const, label: 'Lehrkräfte', icon: UserRoundCog },
            ].map(option => {
              const Icon = option.icon
              const active = mode === option.id
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => switchMode(option.id)}
                  className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium transition-colors"
                  style={{
                    background: active ? 'var(--ink)' : 'transparent',
                    color: active ? 'var(--white)' : 'var(--ink)',
                  }}
                  aria-pressed={active}
                >
                  <Icon size={13} />
                  {option.label}
                </button>
              )
            })}
          </div>
        )}

        {visibleLinks.map(l => (
          <Link
            key={l.href}
            href={l.href}
            className={clsx(
              'text-sm font-medium tracking-wide transition-colors duration-150',
              path.startsWith(l.href)
                ? 'text-[var(--accent)]'
                : 'text-[var(--ink)] hover:text-[var(--accent)]'
            )}
          >
            {l.label}
          </Link>
        ))}

        {/* Language toggle — EN placeholder */}
        <button
          disabled
          title="Englische Version in Vorbereitung"
          className="text-xs font-medium tracking-widest px-3 py-1 rounded-full border opacity-35 cursor-not-allowed select-none"
          style={{ borderColor: 'var(--line)', color: 'var(--ink)' }}
        >
          EN
        </button>
      </nav>
    </header>
  )
}
