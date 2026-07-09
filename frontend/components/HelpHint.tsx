'use client'

// Dauerhafte kontextuelle Hilfe für das Tutor-Backend: kleines ?-Symbol,
// Klick öffnet eine Erklärung. Bewusst persistent (kein einmaliges
// Tutorial), damit auch später dazukommende Tutor:innen sich zurechtfinden.

import { useState } from 'react'

export default function HelpHint({ text, label = 'Hilfe' }: { text: string; label?: string }) {
  const [open, setOpen] = useState(false)

  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        onClick={() => setOpen(v => !v)}
        onBlur={() => setOpen(false)}
        className="ml-1.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold leading-none transition-colors"
        style={{
          border: '1px solid rgba(53,40,30,0.35)',
          color: open ? 'var(--white)' : 'var(--muted)',
          background: open ? 'var(--accent)' : 'transparent',
        }}
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full z-30 mt-2 block w-72 rounded-xl px-3.5 py-3 text-xs font-normal normal-case leading-5 tracking-normal shadow-sm"
          style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
        >
          {text}
        </span>
      )}
    </span>
  )
}
