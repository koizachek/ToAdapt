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
        'Oben siehst du Kennzahlen über alle Studierenden hinweg — sie geben das Gesamtbild, nicht den Einzelfall.',
        'Der Kern ist die Gruppen-Liste unten: Klicke eine Gruppe auf, um zu sehen, wo sie hakt — als Vorbereitung auf deine Präsenzphase.',
        '„Mit Unterstützungsbedarf" heißt: mehrere schwache Lernziele oder sehr niedrige Scores. Sprich Themen an, keine Personen — Einzelprofile siehst du bewusst nicht.',
        'Der Copy-Paste-Anteil ist ein HINWEIS auf mögliche KI-Nutzung, kein Beweis — bitte nie als Vorwurf verwenden.',
        'Alle Zahlen stammen aus der individuellen Vorbereitung im Tool, nicht aus der Gruppenabgabe.',
      ],
    },
    admin: {
      title: 'Admin: Cases erstellen und freigeben',
      steps: [
        'Generieren: Branche, Land und Ziel-TP wählen — die KI erstellt einen vollständigen Entwurf inkl. Bewertungspaket.',
        'Kuratieren: Klappe den Case auf. Der wichtigste Review-Gegenstand sind nicht nur die Texte, sondern Prüfkriterien, Signal-Keywords und Bewertungs-Anker — danach bewertet die KI später die Antworten.',
        'Einzelne Teile kannst du mit einer Anweisung gezielt regenerieren lassen („mehr Zahlen, kürzer").',
        'Prüfen → Freigeben: Der Check blockiert Regelverstöße (z.B. Modellnamen im Text). Erst nach Freigabe sehen Studierende den Case.',
        'Änderungen an freigegebenen Cases setzen den Status zurück — erneute Freigabe nötig.',
      ],
    },
    hint: 'Diese Anleitung findest du jederzeit im Reiter „Anleitung" oben. Die ?-Symbole an den Ansichten erklären jedes Feld.',
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
