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
  briefings: GuideSection
  admin: GuideSection
  hint: string
  dismissLabel: string
}

export const TEACHER_GUIDE: Record<Locale, TeacherGuideContent> = {
  de: {
    pageEyebrow: 'Tutor-Hilfe',
    pageTitle: 'Anleitung',
    pageIntro: 'Alles Wichtige für die Arbeit mit To:Adapt — dauerhaft hier abrufbar. Zusätzlich erklären die ?-Symbole direkt an den Ansichten jedes Feld.',
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
    briefings: {
      title: 'Briefings: Touchpoint vorbereiten in fünf Minuten',
      steps: [
        'Touchpoint wählen, dann „Briefing-Dokument herunterladen" — ein DOCX mit allen Stammgruppen Ihrer Übungsgruppe (Ihre Tutor-Kennung ist Ihre Übungsgruppe, z.B. UEG07).',
        'Je Stammgruppe und Baustein: Kernposition, tragende Argumente, dünne Stellen. Die dünnen Stellen sind als Rückfragen formuliert — daraus ziehen Sie Ihre Spannungslinie.',
        'Die formale Vorprüfung (Zeichengrenzen, Code, Dateiname) wird nur gemeldet, nie bewertet. Es gibt keine Punkte und keine Musterlösung: Jede Wahl ist zulässig, beurteilt wird, ob die Begründung trägt.',
        '„Bitte prüfen" heisst: Die Automatik war unsicher oder hat einen Textteil zurückgehalten — lesen Sie diese Abgabe direkt.',
        'Fehlende Stammgruppen stehen im Kopf des Dokuments. Das Feedback an die Gruppen entsteht erst nach dem Termin.',
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
    briefings: {
      title: 'Briefings: prepare a touchpoint in five minutes',
      steps: [
        'Choose the touchpoint, then "Download briefing document" — one DOCX with all home groups of your tutorial group (your tutor ID is your tutorial group, e.g. UEG07).',
        'Per home group and building block: core position, supporting arguments, thin spots. The thin spots are phrased as follow-up questions — that is where your line of tension comes from.',
        'The formal pre-check (character limits, code, filename) is reported, never graded. There are no points and no model solution: any choice is admissible; only the reasoning is judged.',
        '"Please check" means the automation was unsure or withheld part of the text — read that submission directly.',
        'Missing home groups are listed at the top of the document. Feedback to the groups is created only after the session.',
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
