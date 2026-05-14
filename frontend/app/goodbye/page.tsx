'use client'

import Nav from '@/components/Nav'

const COMPLETION_CODE = 'C17I8JXC'
const PROLIFIC_RETURN_URL = `https://app.prolific.com/submissions/complete?cc=${COMPLETION_CODE}`

export default function GoodbyePage() {
  return (
    <>
      <Nav />
      <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-8 pb-20 pt-28">
        <div
          className="rounded-[32px] border px-8 py-10"
          style={{
            background: 'linear-gradient(135deg, rgba(21,99,61,0.1), rgba(250,250,248,0.96))',
            borderColor: 'rgba(53,40,30,0.14)',
          }}
        >
          <p className="mb-3 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
            Study Complete
          </p>
          <h1 className="font-display text-4xl leading-tight" style={{ color: 'var(--ink)' }}>
            Vielen Dank fuer deine Teilnahme.
          </h1>
          <p className="mt-4 text-sm leading-7" style={{ color: 'var(--ink)' }}>
            Deine Antworten wurden erfolgreich uebermittelt. Nutze jetzt den Completion Code unten oder gehe direkt
            ueber den Button zur Rueckgabe an Prolific.
          </p>

          <div
            className="mt-8 rounded-2xl px-5 py-5"
            style={{ background: 'rgba(53,40,30,0.06)', border: '1px solid rgba(53,40,30,0.1)' }}
          >
            <p className="mb-2 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
              Completion Code
            </p>
            <p className="font-mono text-3xl tracking-[0.18em]" style={{ color: 'var(--ink)' }}>
              {COMPLETION_CODE}
            </p>
          </div>

          <a
            href={PROLIFIC_RETURN_URL}
            className="mt-8 inline-flex items-center justify-center rounded-full px-6 py-3 text-sm font-medium tracking-wide transition-all duration-200"
            style={{ background: 'var(--ink)', color: 'var(--white)' }}
            onMouseEnter={event => { event.currentTarget.style.background = 'var(--accent)' }}
            onMouseLeave={event => { event.currentTarget.style.background = 'var(--ink)' }}
          >
            Zurueck zu Prolific
          </a>
        </div>
      </main>
    </>
  )
}
