// Gemeinsame Inhalte der Tutor-Kurzanleitungen — EINE Quelle für die
// ausblendbaren Panels (Dashboard/Admin) und die dauerhafte Seite /guide.

import { Locale } from '@/lib/i18n'

export interface GuideSection {
  title: string
  steps: string[]
}

export interface TeacherGuideContent {
  pageEyebrow: string
  pageTitle: string
  pageIntro: string
  dashboard: GuideSection
  login: GuideSection
  briefings: GuideSection
  admin: GuideSection
  hint: string
  dismissLabel: string
}

export const TEACHER_GUIDE: Record<Locale, TeacherGuideContent> = {
  de: {
    pageEyebrow: 'Tutor-Hilfe',
    pageTitle: 'Anleitung',
    pageIntro: 'Alles Wichtige für die Arbeit mit To:Adapt, Schritt für Schritt — dauerhaft hier abrufbar. Zusätzlich erklären die ?-Symbole direkt an den Ansichten jede Funktion.',
    dashboard: {
      title: 'Dashboard: Gruppen verstehen in 60 Sekunden',
      steps: [
        'Oben sehen Sie Kennzahlen über alle Studierenden hinweg — sie geben das Gesamtbild, nicht den Einzelfall.',
        'Der Kern ist die Gruppen-Liste unten: Klicken Sie eine Gruppe auf, um zu sehen, wo sie hakt — als Vorbereitung auf Ihre Präsenzphase.',
        '„Mit Unterstützungsbedarf" heißt: mehrere schwache Lernziele oder sehr niedrige Scores. Sprechen Sie Themen an, keine Personen — Einzelprofile sehen Sie bewusst nicht.',
        'Der Copy-Paste-Anteil ist ein HINWEIS auf mögliche KI-Nutzung, kein Beweis — bitte nie als Vorwurf verwenden.',
        'Alle Zahlen stammen aus der individuellen Vorbereitung im Tool, nicht aus der Gruppenabgabe.',
      ],
    },
    login: {
      title: 'Anmelden und Passwort',
      steps: [
        'Ihr Konto heisst UEGL01 bis UEGL26 — die Kursleitung hat es Ihnen mitgeteilt. Gross- oder Kleinschreibung spielt keine Rolle.',
        'Beim allerersten Login wählen Sie Ihr Passwort direkt im Anmeldeformular (mindestens 6 Zeichen) und bestätigen es danach einmal. Ab dann gilt es. Nur Sie kennen es; Ihr Browser darf es sich merken.',
        'Passwort vergessen? Klicken Sie unter dem Anmeldeformular auf „Passwort vergessen?“ und wählen Sie Ihr Konto. Die Kursleitung sieht Ihre Anfrage und schickt Ihnen einen Einmalcode per E-Mail.',
        'Mit dem Einmalcode melden Sie sich einmal an (Code als Passwort eingeben) und legen dann sofort ein neues Passwort fest. Danach ist der Code ungültig.',
        'Nach 12 Stunden werden Sie automatisch abgemeldet. Zum Abmelden vorher: Reiter „Abmelden“ oben rechts.',
      ],
    },
    briefings: {
      title: 'Briefings: Touchpoint vorbereiten in vier Schritten',
      steps: [
        'Hochladen: Packen Sie alle Einreichungen Ihrer Gruppen (PPTX aus der offiziellen Vorlage, ersatzweise DOCX/PDF) in EINE ZIP-Datei und laden Sie sie oben hoch. Touchpoint, Übungsgruppe und Stammgruppe liest das System vom Deckblatt — Sie wählen nichts aus.',
        'Warten: Die Seite zeigt „Verarbeitung läuft: 3 von 16 Dateien“. Sie dürfen die Seite schliessen und später zurückkommen. Pro Datei dauert es etwa eine halbe Minute.',
        'Prüfen: Unter „Nicht ausgewertet“ stehen Dateien ohne Text oder ohne Bezug zum Fall ON — mit Grund; die richtige Datei erneut hochladen. Unter „Bitte zuordnen“ stehen ausgewertete Abgaben, bei denen das Deckblatt fehlte: Übungsgruppe und Stammgruppe eintragen. Bei jeder Auswertung können Sie die erkannten Angaben mit „Angaben ändern“ korrigieren. Ein rotes Ausrufezeichen erscheint, wenn die Gruppen eines Touchpoints von früheren Uploads abweichen oder eine Gruppe versucht hat, die KI mit Anweisungen im Text zu beeinflussen (Prompt-Injection).',
        'Herunterladen: Je Übungsgruppe „Briefing-Dokument (Word)“ — ein Abschnitt je Stammgruppe: Kernposition, tragende Argumente, dünne Stellen als Rückfragen, Einschätzung in Prosa. Dazu „Feedback für die Stammgruppen (ZIP)“ — ein Word-Dokument je Gruppe, das Sie weitergeben, zum Beispiel über Canvas.',
        'Die formale Vorprüfung (Zeichengrenzen, Gruppenangaben, Dateiname) wird nur gemeldet, nie bewertet. Es gibt keine Punkte und keine Musterlösung: Jede Wahl ist zulässig, beurteilt wird, ob die Begründung trägt. „Bitte prüfen“ heisst: Die Automatik war unsicher — lesen Sie diese Abgabe direkt.',
        'Nochmals hochladen ist jederzeit möglich; die neueste Auswertung je Stammgruppe zählt. Abgabedateien und Mitgliedernamen werden nie gespeichert.',
      ],
    },
    admin: {
      title: 'Admin: Cases erstellen und freigeben',
      steps: [
        'Generieren: Branche, Land und Ziel-TP wählen — die KI erstellt einen vollständigen Entwurf inkl. Bewertungspaket.',
        'Kuratieren: Klappen Sie den Case auf. Der wichtigste Review-Gegenstand sind nicht nur die Texte, sondern Prüfkriterien, Signal-Keywords und Bewertungs-Anker — danach bewertet die KI später die Antworten.',
        'Einzelne Teile können Sie mit einer Anweisung gezielt regenerieren lassen („mehr Zahlen, kürzer").',
        'Prüfen → Freigeben: Der Check blockiert Regelverstöße (z.B. Modellnamen im Text). Erst nach Freigabe sehen Studierende den Case.',
        'Änderungen an freigegebenen Cases setzen den Status zurück — erneute Freigabe nötig.',
      ],
    },
    hint: 'Diese Anleitung finden Sie jederzeit im Reiter „Anleitung" oben. Die ?-Symbole an den Ansichten erklären jedes Feld.',
    dismissLabel: 'Verstanden',
  },
  en: {
    pageEyebrow: 'Tutor help',
    pageTitle: 'Guide',
    pageIntro: 'Everything you need for working with To:Adapt — permanently available here. In addition, the ?-icons right next to each view explain every field.',
    dashboard: {
      title: 'Dashboard: understanding groups in 60 seconds',
      steps: [
        'The numbers at the top aggregate across all students — they give the big picture, not individual cases.',
        'The core is the group list below: expand a group to see where it struggles — as preparation for your in-person session.',
        '"Need support" means several weak objectives or very low scores. Address topics, not people — you deliberately never see individual profiles.',
        'The copy-paste share is an INDICATOR of possible AI use, not proof — never use it as an accusation.',
        'All numbers come from individual preparation in the tool, not from the group submission.',
      ],
    },
    login: {
      title: 'Signing in and your password',
      steps: [
        'Your account is UEGL01 to UEGL26 — the course lead gave it to you. Upper or lower case does not matter.',
        'On your very first login you choose your password right in the sign-in form (at least 6 characters) and confirm it once afterwards. From then on it applies. Only you know it; your browser may remember it.',
        'Forgot your password? Click “Forgot your password?” below the sign-in form and choose your account. The course lead sees your request and e-mails you a one-time code.',
        'Sign in once with the one-time code (enter it as the password) and immediately set a new password. Afterwards the code is invalid.',
        'You are signed out automatically after 12 hours. To sign out earlier: “Sign out” at the top right.',
      ],
    },
    briefings: {
      title: 'Briefings: prepare a touchpoint in four steps',
      steps: [
        'Upload: put all submissions of your groups (PPTX from the official template, or DOCX/PDF) into ONE ZIP file and upload it at the top. The system reads touchpoint, tutorial group and home group from the cover sheet — you select nothing.',
        'Wait: the page shows “Processing: 3 of 16 files”. You may close the page and come back later. Each file takes about half a minute.',
        'Check: under “Not evaluated” are files without text or without any link to the ON case — with the reason; upload the correct file again. Under “Please assign” are evaluated submissions whose cover sheet was missing: enter tutorial group and home group. For every result you can correct the detected details with “Change details”. A red warning appears when the groups of a touchpoint differ from earlier uploads or when a group tried to influence the AI with instructions in the text (prompt injection).',
        'Download: per tutorial group “Briefing document (Word)” — one section per home group: core position, supporting arguments, thin spots as follow-up questions, a prose assessment. Plus “Feedback for the home groups (ZIP)” — one Word document per group to pass on, e.g. via Canvas.',
        'The formal pre-check (character limits, group details, filename) is reported, never graded. There are no points and no model solution: any choice is admissible; only the reasoning is judged. “Please check” means the automation was unsure — read that submission directly.',
        'You can upload again at any time; the latest result per home group counts. Submission files and member names are never stored.',
      ],
    },
    admin: {
      title: 'Admin: creating and approving cases',
      steps: [
        'Generate: pick industry, country, and target TP — the AI creates a complete draft including the assessment package.',
        'Curate: expand the case. The most important review targets are not just the texts, but the assessment criteria, signal keywords, and calibration anchors — the AI later grades answers based on them.',
        'You can regenerate individual parts with an instruction ("more numbers, shorter").',
        'Validate → Approve: the check blocks rule violations (e.g. framework names in the text). Students only see the case after approval.',
        'Editing an approved case resets its status — it needs re-approval.',
      ],
    },
    hint: 'You can find this guide at any time in the "Guide" tab above. The ?-icons next to each view explain every field.',
    dismissLabel: 'Got it',
  },
}
