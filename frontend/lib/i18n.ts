export type Locale = 'de' | 'en'

export const DEFAULT_LANGUAGE: Locale = 'de'
export const LANGUAGE_STORAGE_KEY = 'app_language'
export const LANGUAGE_CHANGED_EVENT = 'toadapt:language-changed'

export function isLocale(value: string | null | undefined): value is Locale {
  return value === 'de' || value === 'en'
}

export function languageFromSearchParams(params: URLSearchParams): Locale | null {
  const value = params.get('language') ?? params.get('lang')
  return isLocale(value) ? value : null
}

export function languageFromCaseId(caseId: string): Locale {
  return caseId.endsWith('-en') ? 'en' : 'de'
}

export function caseIdForLanguage(caseId: string, language: Locale): string {
  const baseCaseId = caseId.endsWith('-en') ? caseId.slice(0, -3) : caseId
  return language === 'en' ? `${baseCaseId}-en` : baseCaseId
}

export function readStoredLanguage(): Locale {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE
  const stored = sessionStorage.getItem(LANGUAGE_STORAGE_KEY)
  return isLocale(stored) ? stored : DEFAULT_LANGUAGE
}

export function writeStoredLanguage(language: Locale) {
  if (typeof window === 'undefined') return

  sessionStorage.setItem(LANGUAGE_STORAGE_KEY, language)

  try {
    const experimentContext = JSON.parse(sessionStorage.getItem('experiment_context') ?? 'null')
    if (experimentContext) {
      sessionStorage.setItem('experiment_context', JSON.stringify({
        ...experimentContext,
        metadata: {
          ...(experimentContext.metadata ?? {}),
          language,
        },
      }))
    }
  } catch {
    // Ignore malformed legacy session data.
  }

  window.dispatchEvent(new CustomEvent(LANGUAGE_CHANGED_EVENT, { detail: { language } }))
}

export function languageQuery(language: Locale) {
  return `language=${language}`
}
