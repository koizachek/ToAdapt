'use client'

// Ausblendbare Kurzanleitung am Kopf der Tutor-Seiten (Dashboard/Admin).
// Einmal weggeklickt bleibt sie weg (localStorage), die ?-Symbole (HelpHint)
// bleiben als dauerhafte Hilfe bestehen.

import { useState } from 'react'
import NotionIcon from '@/components/NotionIcon'

export default function TeacherIntro({
  storageKey,
  title,
  steps,
  hint,
  dismissLabel,
}: {
  storageKey: string
  title: string
  steps: string[]
  hint: string
  dismissLabel: string
}) {
  const [visible, setVisible] = useState(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem(storageKey) !== 'dismissed'
  })

  if (!visible) return null

  return (
    <section
      className="mb-10 rounded-2xl p-6"
      style={{ background: 'rgba(21,99,61,0.06)', border: '1px solid rgba(53,40,30,0.14)' }}
    >
      <div className="mb-3 flex items-start justify-between gap-4">
        <p className="flex items-center gap-2.5 text-sm font-medium">
          <NotionIcon name="guide" size={26} />
          {title}
        </p>
        <button
          type="button"
          onClick={() => {
            localStorage.setItem(storageKey, 'dismissed')
            setVisible(false)
          }}
          className="shrink-0 px-3 py-1.5 text-xs font-medium"
          style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
        >
          {dismissLabel}
        </button>
      </div>
      <ol className="mb-3 flex flex-col gap-1.5 pl-1">
        {steps.map((step, i) => (
          <li key={i} className="flex gap-2.5 text-xs leading-5">
            <span className="shrink-0 font-mono" style={{ color: 'var(--accent)' }}>{i + 1}.</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <p className="text-xs" style={{ color: 'var(--muted)' }}>{hint}</p>
    </section>
  )
}
