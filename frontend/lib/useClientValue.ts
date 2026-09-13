'use client'

// Hydration-sicheres Lesen von Browser-Zustand (Cookies, sessionStorage).
//
// Ein useState-Initializer, der Cookies liest, liefert auf dem Server einen
// anderen Wert als im Browser → React meldet "Hydration failed" und rendert
// den Baum neu. useSyncExternalStore kennt dafür einen Server-Snapshot: Der
// Server (und der allererste Client-Render) sehen `serverValue`, danach den
// echten Browser-Wert — ohne setState im Effekt.

import { useSyncExternalStore } from 'react'

const subscribe = () => () => {}

export function useClientValue<T>(read: () => T, serverValue: T): T {
  return useSyncExternalStore(subscribe, read, () => serverValue)
}
