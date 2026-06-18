export type AppMode = 'student' | 'teacher'

export const APP_MODE_STORAGE_KEY = 'app_mode'
export const APP_MODE_CHANGED_EVENT = 'toadapt:app-mode-changed'

export function hasCookie(name: string, value: string) {
  if (typeof document === 'undefined') return false
  return document.cookie.split(';').some(cookie => cookie.trim() === `${name}=${value}`)
}

export function clearCookie(name: string) {
  if (typeof document === 'undefined') return
  document.cookie = `${name}=; Max-Age=0; path=/`
}

export function readTeacherMode() {
  if (typeof window === 'undefined') return false

  try {
    if (sessionStorage.getItem(APP_MODE_STORAGE_KEY) === 'student') {
      return false
    }
  } catch {
    return false
  }

  return hasCookie('teacher_mode', 'true')
}

export function readStoredAppMode(): AppMode {
  if (typeof window === 'undefined') return 'student'
  if (readTeacherMode()) return 'teacher'

  try {
    return sessionStorage.getItem(APP_MODE_STORAGE_KEY) === 'teacher' ? 'teacher' : 'student'
  } catch {
    return 'student'
  }
}

export function writeAppMode(mode: AppMode) {
  if (typeof window === 'undefined') return

  if (mode === 'student') {
    clearCookie('teacher_mode')
  }

  sessionStorage.setItem(APP_MODE_STORAGE_KEY, mode)
  window.dispatchEvent(new CustomEvent(APP_MODE_CHANGED_EVENT, { detail: { mode } }))
}
