'use client'

// Login-Formular für Übungsgruppenleiter und Master.
// Drei Ansichten, gesteuert über URL-Parameter, die /teacher-login setzt:
//   login          Konto + Passwort (+ Link "Passwort vergessen")
//   confirm_password  Erster Login: das eingegebene Passwort einmal wiederholen
//   set_password      Nach Einmalcode: neues Passwort, zweimal eingeben
//   reset_request  Konto wählen → Master wird benachrichtigt
// Jede Funktion hat ein ?-Symbol mit Erklärung in einfacher Sprache.

import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import HelpHint from '@/components/HelpHint'
import type { Locale } from '@/lib/i18n'

export type TeacherLoginView = 'login' | 'confirm_password' | 'set_password' | 'reset_request'

interface Props {
  language: Locale
  view: TeacherLoginView
  account?: string
  error?: string
  notice?: string
}

const TEXT = {
  de: {
    section: 'Übungsgruppenleitung',
    account: 'Konto',
    accountPlaceholder: 'z.B. UEGL05',
    accountHelp: 'Ihr Konto hat die Kursleitung Ihnen mitgeteilt: UEGL01 bis UEGL26. Gross- oder Kleinschreibung spielt keine Rolle.',
    password: 'Passwort',
    passwordPlaceholder: 'Ihr Passwort',
    passwordHelp: 'Beim allerersten Login wählen Sie hier einfach Ihr Passwort (mindestens 6 Zeichen) und bestätigen es danach einmal. Ab dann gilt es. Ihr Browser darf es sich merken.',
    submit: 'Anmelden',
    forgot: 'Passwort vergessen?',
    forgotHelp: 'Die Kursleitung sieht Ihre Anfrage und schickt Ihnen einen Einmalcode per E-Mail. Mit diesem Code melden Sie sich einmal an und legen dann ein neues Passwort fest.',
    confirmTitle: (account: string) => `Willkommen, ${account}`,
    confirmIntro: 'Das ist Ihr erster Login. Das eben eingegebene Passwort gilt ab jetzt für Ihr Konto. Bitte geben Sie es zur Sicherheit noch einmal ein.',
    confirmField: 'Passwort wiederholen',
    confirmSubmit: 'Bestätigen und anmelden',
    setTitle: (account: string) => `Neues Passwort festlegen für ${account}`,
    setIntro: 'Wählen Sie ein neues Passwort mit mindestens 6 Zeichen und geben Sie es zweimal ein. Nur Sie kennen es — die Kursleitung sieht es nie.',
    newPassword: 'Neues Passwort (mindestens 6 Zeichen)',
    repeatPassword: 'Passwort wiederholen',
    setSubmit: 'Passwort speichern und anmelden',
    resetTitle: 'Passwort vergessen',
    resetIntro: 'Wählen Sie Ihr Konto. Die Kursleitung wird benachrichtigt und schickt Ihnen einen Einmalcode per E-Mail. Geben Sie den Code dann beim Anmelden als Passwort ein.',
    resetSubmit: 'Kursleitung benachrichtigen',
    backToLogin: 'Zurück zur Anmeldung',
    noticeReset: (account: string) => `Anfrage für ${account} ist bei der Kursleitung eingegangen. Sie erhalten einen Einmalcode per E-Mail.`,
    errors: {
      '1': 'Passwort nicht korrekt.',
      rate: 'Zu viele Versuche — bitte eine Minute warten.',
      unknown: 'Dieses Konto gibt es nicht. Gültig sind UEGL01 bis UEGL26.',
      short: 'Das Passwort muss mindestens 6 Zeichen haben.',
      mismatch: 'Die beiden Passwörter stimmen nicht überein.',
      exists: 'Dieses Konto hat bereits ein Passwort. Bitte anmelden oder „Passwort vergessen“ wählen.',
      expired: 'Die Bestätigung hat zu lange gedauert. Bitte noch einmal anmelden.',
      backend: 'Anmeldung derzeit nicht möglich — bitte später erneut versuchen.',
    } as Record<string, string>,
  },
  en: {
    section: 'Tutorial group leads',
    account: 'Account',
    accountPlaceholder: 'e.g. UEGL05',
    accountHelp: 'The course lead gave you your account: UEGL01 to UEGL26. Upper or lower case does not matter.',
    password: 'Password',
    passwordPlaceholder: 'Your password',
    passwordHelp: 'On your very first login simply choose your password here (at least 6 characters) and confirm it once afterwards. From then on it applies. Your browser may remember it.',
    submit: 'Sign in',
    forgot: 'Forgot your password?',
    forgotHelp: 'The course lead sees your request and e-mails you a one-time code. Sign in once with that code and then set a new password.',
    confirmTitle: (account: string) => `Welcome, ${account}`,
    confirmIntro: 'This is your first login. The password you just entered now applies to your account. Please enter it once more to be safe.',
    confirmField: 'Repeat password',
    confirmSubmit: 'Confirm and sign in',
    setTitle: (account: string) => `Set a new password for ${account}`,
    setIntro: 'Choose a new password with at least 6 characters and enter it twice. Only you know it — the course lead never sees it.',
    newPassword: 'New password (at least 6 characters)',
    repeatPassword: 'Repeat password',
    setSubmit: 'Save password and sign in',
    resetTitle: 'Forgot password',
    resetIntro: 'Choose your account. The course lead is notified and e-mails you a one-time code. Enter that code as your password when signing in.',
    resetSubmit: 'Notify the course lead',
    backToLogin: 'Back to sign-in',
    noticeReset: (account: string) => `The request for ${account} has reached the course lead. You will receive a one-time code by e-mail.`,
    errors: {
      '1': 'Incorrect password.',
      rate: 'Too many attempts — please wait a minute.',
      unknown: 'This account does not exist. Valid accounts are UEGL01 to UEGL26.',
      short: 'The password needs at least 6 characters.',
      mismatch: 'The two passwords do not match.',
      exists: 'This account already has a password. Please sign in or choose “Forgot your password?”.',
      expired: 'The confirmation took too long. Please sign in again.',
      backend: 'Sign-in is not possible right now — please try again later.',
    } as Record<string, string>,
  },
}

const ERROR_TONE = '#c0392b'

const fieldStyle = { background: 'var(--field)', border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }
const onFocus = (e: React.FocusEvent<HTMLInputElement>) => { e.currentTarget.style.borderColor = 'var(--accent)' }
const onBlur = (e: React.FocusEvent<HTMLInputElement>) => { e.currentTarget.style.borderColor = 'rgba(53,40,30,0.25)' }

function Label({ children, help }: { children: React.ReactNode; help?: string }) {
  return (
    <label className="block text-xs mb-2 font-medium tracking-wide" style={{ color: 'var(--line)' }}>
      {children}
      {help && <HelpHint text={help} />}
    </label>
  )
}

function Submit({ children }: { children: React.ReactNode }) {
  return (
    <button
      type="submit"
      className="group flex items-center justify-between px-5 py-3 text-sm font-medium tracking-wide transition-all duration-200"
      style={{ background: 'var(--ink)', color: 'var(--white)' }}
      onMouseEnter={event => { event.currentTarget.style.background = 'var(--accent)' }}
      onMouseLeave={event => { event.currentTarget.style.background = 'var(--ink)' }}
    >
      {children}
      <ArrowRight size={15} className="transition-transform duration-200 group-hover:translate-x-1" />
    </button>
  )
}

export default function TeacherLoginForm({ language, view, account = '', error = '', notice = '' }: Props) {
  const text = TEXT[language]
  const [mode, setMode] = useState<TeacherLoginView>(view)
  const errorText = error ? text.errors[error] ?? text.errors.backend : ''

  if (mode === 'confirm_password') {
    return (
      <form action="/teacher-login" method="post" className="flex flex-col gap-4">
        <input type="hidden" name="language" value={language} />
        <input type="hidden" name="action" value="confirm_password" />
        <input type="hidden" name="account" value={account} />
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted)' }}>{text.confirmTitle(account)}</p>
        <p className="text-xs leading-5" style={{ color: 'var(--muted)' }}>{text.confirmIntro}</p>
        <div>
          <Label>{text.confirmField}</Label>
          <input type="password" name="password_repeat" required autoFocus autoComplete="new-password"
            className="w-full px-4 py-3 text-sm outline-none transition-all" style={fieldStyle} onFocus={onFocus} onBlur={onBlur} />
          {errorText && <p className="mt-2 text-xs" style={{ color: ERROR_TONE }}>{errorText}</p>}
        </div>
        <Submit>{text.confirmSubmit}</Submit>
        <button type="button" className="text-xs underline-offset-2 hover:underline text-left" style={{ color: 'var(--muted)' }}
          onClick={() => setMode('login')}>
          {text.backToLogin}
        </button>
      </form>
    )
  }

  if (mode === 'set_password') {
    return (
      <form action="/teacher-login" method="post" className="flex flex-col gap-4">
        <input type="hidden" name="language" value={language} />
        <input type="hidden" name="action" value="set_password" />
        <input type="hidden" name="account" value={account} />
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted)' }}>{text.setTitle(account)}</p>
        <p className="text-xs leading-5" style={{ color: 'var(--muted)' }}>{text.setIntro}</p>
        <div>
          <Label>{text.newPassword}</Label>
          <input type="password" name="password" minLength={6} required autoComplete="new-password"
            className="w-full px-4 py-3 text-sm outline-none transition-all" style={fieldStyle} onFocus={onFocus} onBlur={onBlur} />
        </div>
        <div>
          <Label>{text.repeatPassword}</Label>
          <input type="password" name="password_repeat" minLength={6} required autoComplete="new-password"
            className="w-full px-4 py-3 text-sm outline-none transition-all" style={fieldStyle} onFocus={onFocus} onBlur={onBlur} />
          {errorText && <p className="mt-2 text-xs" style={{ color: ERROR_TONE }}>{errorText}</p>}
        </div>
        <Submit>{text.setSubmit}</Submit>
        <button type="button" className="text-xs underline-offset-2 hover:underline text-left" style={{ color: 'var(--muted)' }}
          onClick={() => setMode('login')}>
          {text.backToLogin}
        </button>
      </form>
    )
  }

  if (mode === 'reset_request') {
    return (
      <form action="/teacher-login" method="post" className="flex flex-col gap-4">
        <input type="hidden" name="language" value={language} />
        <input type="hidden" name="action" value="reset_request" />
        <p className="text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted)' }}>{text.resetTitle}</p>
        <p className="text-xs leading-5" style={{ color: 'var(--muted)' }}>{text.resetIntro}</p>
        <div>
          <Label help={text.accountHelp}>{text.account}</Label>
          <input name="account" defaultValue={account} placeholder={text.accountPlaceholder} required autoComplete="username"
            className="w-full px-4 py-3 text-sm outline-none transition-all" style={fieldStyle} onFocus={onFocus} onBlur={onBlur} />
          {errorText && <p className="mt-2 text-xs" style={{ color: ERROR_TONE }}>{errorText}</p>}
        </div>
        <Submit>{text.resetSubmit}</Submit>
        <button type="button" className="text-xs underline-offset-2 hover:underline text-left" style={{ color: 'var(--muted)' }}
          onClick={() => setMode('login')}>
          {text.backToLogin}
        </button>
      </form>
    )
  }

  return (
    <form action="/teacher-login" method="post" className="flex flex-col gap-4">
      <input type="hidden" name="language" value={language} />
      <input type="hidden" name="action" value="login" />
      <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.section}</p>
      {notice === 'reset_requested' && (
        <p className="text-xs leading-5 p-3" style={{ background: 'rgba(21,99,61,0.08)', color: 'var(--ink)' }}>
          {text.noticeReset(account || '—')}
        </p>
      )}
      <div>
        <Label help={text.accountHelp}>{text.account}</Label>
        <input name="account" defaultValue={account} placeholder={text.accountPlaceholder} required autoComplete="username"
          className="w-full px-4 py-3 text-sm outline-none transition-all" style={fieldStyle} onFocus={onFocus} onBlur={onBlur} />
      </div>
      <div>
        <Label help={text.passwordHelp}>{text.password}</Label>
        <input type="password" name="password" placeholder={text.passwordPlaceholder} required autoComplete="current-password"
          className="w-full px-4 py-3 text-sm outline-none transition-all" style={fieldStyle} onFocus={onFocus} onBlur={onBlur} />
        {errorText && <p className="mt-2 text-xs" style={{ color: ERROR_TONE }}>{errorText}</p>}
      </div>
      <Submit>{text.submit}</Submit>
      <p className="text-xs flex items-center" style={{ color: 'var(--muted)' }}>
        <button type="button" className="underline-offset-2 hover:underline" style={{ color: 'var(--muted)' }}
          onClick={() => setMode('reset_request')}>
          {text.forgot}
        </button>
        <HelpHint text={text.forgotHelp} />
      </p>
    </form>
  )
}
