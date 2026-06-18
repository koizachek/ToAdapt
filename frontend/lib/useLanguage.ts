'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  LANGUAGE_CHANGED_EVENT,
  Locale,
  readStoredLanguage,
  writeStoredLanguage,
} from '@/lib/i18n'

export function useLanguage() {
  const [language, setLanguageState] = useState<Locale>(() => readStoredLanguage())

  useEffect(() => {
    const syncLanguage = () => setLanguageState(readStoredLanguage())
    window.addEventListener(LANGUAGE_CHANGED_EVENT, syncLanguage)
    window.addEventListener('storage', syncLanguage)
    return () => {
      window.removeEventListener(LANGUAGE_CHANGED_EVENT, syncLanguage)
      window.removeEventListener('storage', syncLanguage)
    }
  }, [])

  const setLanguage = useCallback((nextLanguage: Locale) => {
    writeStoredLanguage(nextLanguage)
    setLanguageState(nextLanguage)
  }, [])

  return [language, setLanguage] as const
}
