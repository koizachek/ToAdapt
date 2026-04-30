'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import clsx from 'clsx'

const links = [
  { href: '/cases', label: 'Cases' },
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/admin', label: 'Admin' },
]

export default function Nav() {
  const path = usePathname()

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-5"
      style={{ borderBottom: '1px solid rgba(53,40,30,0.12)', background: 'rgba(223,221,214,0.92)', backdropFilter: 'blur(12px)' }}
    >
      {/* Wordmark */}
      <Link href="/" className="font-display text-xl tracking-tight" style={{ color: 'var(--ink)' }}>
        ToAdapt
      </Link>

      {/* Nav links */}
      <nav className="flex items-center gap-8">
        {links.map(l => (
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
