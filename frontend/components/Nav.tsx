'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import clsx from 'clsx'
import { useState } from 'react'
import { GraduationCap, LogOut, UserRoundCog } from 'lucide-react'
import {
  AppMode,
  readStoredAppMode,
  readStudentIdentity,
  readTeacherMaster,
  readTeacherMode,
  writeAppMode,
} from '@/lib/appMode'
import { caseIdForLanguage, Locale } from '@/lib/i18n'
import { useLanguage } from '@/lib/useLanguage'

const studentLinks = [
  { href: '/cases', label: 'Cases' },
]

const teacherLinks = (language: Locale, isMaster: boolean) => [
  { href: '/cases', label: 'Cases' },
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/guide', label: language === 'en' ? 'Guide' : 'Anleitung' },
  { href: '/admin', label: 'Admin' },
  // Nur der Master-Tutor (Login mit dem Master-Code) sieht den Upload-Reiter
  // für die außerhalb der Plattform erstellten Gruppenarbeiten.
  ...(isMaster ? [{ href: '/upload', label: 'Upload' }] : []),
]

const NAV_TEXT: Record<Locale, {
  modeAria: string
  studentMode: string
  teacherMode: string
  languageAria: string
  logout: string
}> = {
  de: {
    modeAria: 'Modus wählen',
    studentMode: 'Studierende',
    teacherMode: 'Lehrkräfte',
    languageAria: 'Sprache wählen',
    logout: 'Abmelden',
  },
  en: {
    modeAria: 'Choose mode',
    studentMode: 'Students',
    teacherMode: 'Teachers',
    languageAria: 'Choose language',
    logout: 'Log out',
  },
}

function modeFromPath(path: string): AppMode | null {
  if (path.startsWith('/dashboard') || path.startsWith('/admin') || path.startsWith('/guide') || path.startsWith('/upload')) return 'teacher'
  if (path.startsWith('/results') || path.startsWith('/goodbye')) return 'student'
  return null
}

export default function Nav() {
  const path = usePathname()
  const router = useRouter()
  const [language, setLanguage] = useLanguage()
  const [selectedMode, setSelectedMode] = useState<AppMode>(() => readStoredAppMode())
  const [isExperimentalRun] = useState(() => {
    if (typeof window === 'undefined') return false
    if (readTeacherMode()) return false
    try {
      const experimentContext = JSON.parse(sessionStorage.getItem('experiment_context') ?? 'null')
      return experimentContext?.provider === 'prolific'
    } catch {
      return false
    }
  })
  const [hasTeacherAccess, setHasTeacherAccess] = useState(() => {
    if (typeof window === 'undefined') return false
    return readTeacherMode()
  })
  const [hasStudentIdentity] = useState(() => readStudentIdentity())
  const [isMasterTutor] = useState(() => readTeacherMaster())
  const text = NAV_TEXT[language]
  const mode = hasTeacherAccess ? 'teacher' : isExperimentalRun ? 'student' : modeFromPath(path) ?? selectedMode

  // Sobald man in einer Rolle eingeloggt ist (Studierenden-Identität oder
  // Lehrkraft-Cookie), darf der Modus nicht mehr per Klick umgeschaltet werden —
  // sonst setzt ein versehentlicher Klick den ganzen Zustand zurück. Ein
  // bewusster Rollenwechsel bleibt über das ToAdapt-Wortmark → Startseite möglich.
  const roleLocked = hasTeacherAccess || hasStudentIdentity || isExperimentalRun

  const visibleLinks = !hasTeacherAccess && (isExperimentalRun || mode === 'student')
    ? studentLinks
    : teacherLinks(language, isMasterTutor)

  const switchMode = (nextMode: AppMode) => {
    if (nextMode === 'student') {
      writeAppMode('student')
      setSelectedMode('student')
      setHasTeacherAccess(false)
      router.push('/cases')
      return
    }

    if (nextMode === 'teacher' && !hasTeacherAccess) {
      writeAppMode('teacher')
      setSelectedMode('teacher')
      router.push('/')
      return
    }

    writeAppMode(nextMode)
    setSelectedMode(nextMode)
    setHasTeacherAccess(readTeacherMode())
    router.push(nextMode === 'teacher' ? '/dashboard' : '/cases')
  }

  const switchLanguage = (nextLanguage: Locale) => {
    setLanguage(nextLanguage)

    const caseMatch = path.match(/^\/cases\/([^/]+)$/)
    if (caseMatch) {
      router.push(`/cases/${caseIdForLanguage(caseMatch[1], nextLanguage)}`)
      return
    }

    if (path === '/') {
      router.refresh()
    }
  }

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between gap-6 px-8 py-5"
      style={{ borderBottom: '1px solid var(--hairline)', background: 'rgba(228,226,220,0.92)', backdropFilter: 'blur(12px)' }}
    >
      {/* Wordmark */}
      <Link href="/" className="font-display text-xl tracking-tight" style={{ color: 'var(--ink)' }}>
        ToAdapt
      </Link>

      {/* Nav links */}
      <nav className="flex items-center gap-8">
        {!roleLocked && (
          <div
            className="flex items-center gap-1 p-1"
            style={{ border: '1px solid var(--hairline)', background: 'var(--field)' }}
            aria-label={text.modeAria}
          >
            {[
              { id: 'student' as const, label: text.studentMode, icon: GraduationCap },
              { id: 'teacher' as const, label: text.teacherMode, icon: UserRoundCog },
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

        {hasTeacherAccess && (
          // Form-POST statt fetch: Der Server löscht das httpOnly-Session-Cookie
          // und leitet auf die Login-Seite um — funktioniert auch ohne JS.
          <form method="post" action="/teacher-logout">
            <input type="hidden" name="language" value={language} />
            <button
              type="submit"
              className="flex items-center gap-2 text-sm font-medium tracking-wide transition-colors duration-150 text-[var(--ink)] hover:text-[var(--accent)]"
            >
              <LogOut size={13} />
              {text.logout}
            </button>
          </form>
        )}

        <div
          className="flex items-center gap-1 p-1"
          style={{ border: '1px solid var(--hairline)', background: 'var(--field)' }}
          aria-label={text.languageAria}
        >
          {(['de', 'en'] as Locale[]).map(option => {
            const active = language === option
            return (
              <button
                key={option}
                type="button"
                onClick={() => switchLanguage(option)}
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
      </nav>
    </header>
  )
}
