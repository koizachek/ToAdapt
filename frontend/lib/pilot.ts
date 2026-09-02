// Pilotphase HS26: Nur die Tutorenansicht ist sichtbar.
//
// Der Studierenden-Flow (Cases, Chat, Submissions), die Case-Ansicht, der
// Case-Generator (Admin) und das Individual-Dashboard bleiben im Code, werden
// aber nicht angezeigt. Sichtbar: Login, Briefings (ÜGL: eigene Übungs-
// gruppen; Master: zusätzlich Upload) und die Anleitung.
//
// Standard AN. Ausschalten (spätere Freischaltung der Studierenden) über die
// Build-Env NEXT_PUBLIC_PILOT_TUTOR_ONLY=0 auf Vercel. Backend-Pendant:
// PILOT_TUTOR_ONLY (Railway) sperrt die Studierenden-API und den Generator.
export const PILOT_TUTOR_ONLY = process.env.NEXT_PUBLIC_PILOT_TUTOR_ONLY !== '0'

/** Startseite nach dem Tutor-Login. */
export const TEACHER_HOME = PILOT_TUTOR_ONLY ? '/briefings' : '/cases'
