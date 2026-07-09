'use client'

// Dauerhafte Anleitungs-Seite für Tutor:innen — Reiter "Anleitung" in der
// Nav. Inhalte kommen aus lib/teacherGuide.ts (eine Quelle, geteilt mit
// den ausblendbaren Panels auf Dashboard/Admin). Middleware-geschützt.

import Link from 'next/link'
import { useEffect } from 'react'
import Nav from '@/components/Nav'
import NotionIcon from '@/components/NotionIcon'
import { APP_MODE_STORAGE_KEY } from '@/lib/appMode'
import { TEACHER_GUIDE } from '@/lib/teacherGuide'
import { useLanguage } from '@/lib/useLanguage'

export default function GuidePage() {
  const [language] = useLanguage()
  const guide = TEACHER_GUIDE[language]

  useEffect(() => {
    sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'teacher')
  }, [])

  const sections = [
    { icon: 'dashboard', href: '/dashboard', section: guide.dashboard },
    { icon: 'generator', href: '/admin', section: guide.admin },
  ]

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-3xl mx-auto">
        <div className="mb-10">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
            {guide.pageEyebrow}
          </p>
          <h1 className="font-display text-5xl leading-none flex items-center gap-4">
            <NotionIcon name="guide" size={44} />
            {guide.pageTitle}
          </h1>
          <p className="mt-4 text-sm leading-6" style={{ color: 'var(--muted)' }}>
            {guide.pageIntro}
          </p>
        </div>

        <div className="divider mb-10" />

        <div className="flex flex-col gap-8">
          {sections.map(({ icon, href, section }) => (
            <section
              key={href}
              className="rounded-2xl p-7"
              style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.14)' }}
            >
              <Link
                href={href}
                className="mb-4 flex items-center gap-3 text-sm font-medium hover:text-[var(--accent)] transition-colors"
              >
                <NotionIcon name={icon} size={28} />
                {section.title}
              </Link>
              <ol className="flex flex-col gap-2">
                {section.steps.map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm leading-6">
                    <span className="shrink-0 font-mono text-xs mt-0.5" style={{ color: 'var(--accent)' }}>
                      {i + 1}.
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      </main>
    </>
  )
}
