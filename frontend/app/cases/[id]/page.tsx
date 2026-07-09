'use client'

import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, usePathname, useRouter } from 'next/navigation'
import clsx from 'clsx'
import { BookOpenText, FileText, MessageSquare, Send } from 'lucide-react'
import Nav from '@/components/Nav'
import NotionIcon from '@/components/NotionIcon'
import { apiFetch } from '@/lib/api'
import {
  APP_MODE_CHANGED_EVENT,
  APP_MODE_STORAGE_KEY,
  clearCookie,
  readTeacherMode,
} from '@/lib/appMode'
import { isLocale, languageFromCaseId, Locale } from '@/lib/i18n'
import { useLanguage } from '@/lib/useLanguage'

interface CaseSection { section_id: string; title: string; content: string }
interface CaseExhibit { exhibit_id: string; title: string; content: string; exhibit_type: string }
interface CaseCanvasBlockSpec { block: string; label: string; expectation: string }
interface CaseQuestion {
  question_id: string; phase: number; bloom_level: number; text: string; max_points: number
  min_words?: number | null
  max_words?: number | null
  required_canvas_blocks?: CaseCanvasBlockSpec[]
}
interface CaseGlossaryTerm { term: string; explanation: string; starter_prompt: string }
interface Case {
  case_id: string
  title: string
  industry: string
  country: string
  tagline: string
  sections: CaseSection[]
  exhibits: CaseExhibit[]
  questions: CaseQuestion[]
  glossary?: CaseGlossaryTerm[]
  target_tp?: number
  language?: string
}
interface ChatMsg { role: 'user' | 'agent'; content: string; agent_type?: string }
interface ExperimentContext {
  provider?: string
  experiment_name?: string
  run_id?: string
  condition?: string
  prolific_pid?: string
  prolific_study_id?: string
  prolific_session_id?: string
  metadata?: Record<string, string>
}
interface GlossaryTerm {
  term: string
  explanation: string
  starterPrompt: string
}
interface ParsedExhibitTable {
  headers: string[]
  rows: string[][]
  notes: string[]
}
interface AnswerRequirement {
  minWords: number
  maxWords: number
}
interface ClientIdentity {
  userId: string
  participantId: string
  experiment: ExperimentContext | null
}

interface CanvasBlock {
  key: string
  label: string
  hint: string
}

type GlossaryHighlightTargets = Map<string, string>

const AGENT_LABEL: Record<Locale, Record<string, string>> = {
  de: {
    metacognitive: 'Reflexion',
    strategic: 'Strategie',
    conceptual: 'Konzept',
    procedural: 'Format',
  },
  en: {
    metacognitive: 'Reflection',
    strategic: 'Strategy',
    conceptual: 'Concept',
    procedural: 'Format',
  },
}

const BUSINESS_MODEL_CANVAS_BLOCKS: Record<Locale, CanvasBlock[]> = {
  de: [
    { key: 'value_propositions', label: 'Value Propositions', hint: 'Welchen konkreten Nutzen verspricht Alpes Bank ihren Kundinnen und Kunden?' },
    { key: 'customer_segments', label: 'Customer Segments', hint: 'Welche Kundengruppen sind besonders relevant oder betroffen?' },
    { key: 'channels', label: 'Channels', hint: 'Über welche Kanäle wird Leistung erbracht oder verändert sich der Zugang?' },
    { key: 'customer_relationships', label: 'Customer Relationships', hint: 'Wie verändert sich die Kundenbeziehung, Beratung oder das Vertrauen?' },
    { key: 'revenue_streams', label: 'Revenue Streams', hint: 'Welche Ertragslogik wird gestärkt, bedroht oder verändert?' },
    { key: 'key_resources', label: 'Key Resources', hint: 'Welche Ressourcen, Fähigkeiten, Daten oder Kompetenzen tragen die Lösung?' },
    { key: 'key_activities', label: 'Key Activities', hint: 'Welche zentralen Aktivitäten oder Prozesse müssen neu gestaltet werden?' },
    { key: 'key_partners', label: 'Key Partners', hint: 'Welche Partner spielen eine tragende Rolle für Umsetzung oder Risiko?' },
    { key: 'cost_structure', label: 'Cost Structure', hint: 'Welche Kosten-, Effizienz- oder Investitionsfolgen sind zentral?' },
  ],
  en: [
    { key: 'value_propositions', label: 'Value Propositions', hint: 'What concrete value does Alpes Bank promise to its customers?' },
    { key: 'customer_segments', label: 'Customer Segments', hint: 'Which customer groups are especially relevant or affected?' },
    { key: 'channels', label: 'Channels', hint: 'Through which channels is value delivered, or how does access change?' },
    { key: 'customer_relationships', label: 'Customer Relationships', hint: 'How do advice, trust, or the customer relationship change?' },
    { key: 'revenue_streams', label: 'Revenue Streams', hint: 'Which revenue logic is strengthened, threatened, or changed?' },
    { key: 'key_resources', label: 'Key Resources', hint: 'Which resources, capabilities, data, or competencies support the solution?' },
    { key: 'key_activities', label: 'Key Activities', hint: 'Which core activities or processes need to be redesigned?' },
    { key: 'key_partners', label: 'Key Partners', hint: 'Which partners are central for implementation or risk?' },
    { key: 'cost_structure', label: 'Cost Structure', hint: 'Which cost, efficiency, or investment effects matter most?' },
  ],
}

const CASE_PAGE_TEXT = {
  de: {
    loading: 'Wird geladen...',
    taskMaterials: 'Task Materials',
    questions: 'Fragen',
    teacherPreview: 'Lehrkräfte-Vorschau',
    exhibits: 'Exhibits',
    canvasEyebrow: 'Verbindlicher Analyserahmen',
    canvasTitle: 'Business Model Canvas',
    canvasRequired: 'Pflicht für die Bearbeitung',
    canvasIntro: 'Bearbeite die Fragen auf Basis des Business Model Canvas. Strukturiere deine Antwort entlang der relevanten Canvas-Bausteine und zeige, wie sich Entscheidung, Risiko und Wirkung auf das Geschäftsmodell von Alpes Bank auswirken.',
    canvasQuality: 'Gute Antworten nennen nicht nur Begriffe, sondern wenden die passenden Canvas-Bausteine konkret auf den Fall an. Entscheidend ist, wie sauber du den Zusammenhang zwischen Geschäftsmodell, Wettbewerb, Umsetzung und Risiko erklärst.',
    answerRule: 'Schreibe in ganzen Sätzen. Für Frage 1-2 gilt 50-200 Wörter, für Frage 3-4 100-200 Wörter.',
    points: 'Pkt',
    teacherAnswerRequirement: (min: number, max: number) => `Antwortvorgabe fuer Studierende: ${min}-${max} Woerter, ganze Saetze.`,
    answerPlaceholder: (min: number, max: number) => `Deine Antwort in ganzen Sätzen (${min}-${max} Wörter)...`,
    requirement: (min: number, max: number) => `Vorgabe: ${min}-${max} Wörter, ganze Sätze`,
    words: (count: number) => `${count} Wörter`,
    sentenceHint: 'Bitte in ganzen Sätzen formulieren.',
    invalidQuestion: (index: number, min: number, max: number) => `Frage ${index + 1} muss zwischen ${min} und ${max} Wörtern liegen.`,
    evaluationError: 'Die Auswertung konnte nicht abgeschlossen werden.',
    evaluating: 'Auswertung laeuft. Bitte Seite nicht schliessen.',
    submit: 'Abgeben & auswerten',
    submitting: 'Wird ausgewertet...',
    preview: 'Vorschau',
    industry: 'Branche',
    country: 'Land',
    sections: 'Abschnitte',
    showQuestions: 'Fragen anzeigen',
    learningChat: 'Lernchat',
    chatIntro: 'Markierte Begriffe starten eine gezielte Diskussion, ohne dass du den Lesekontext verlierst.',
    activeTopic: 'Aktives Thema',
    askAgent: 'Frag den Agenten zum Material...',
    writing: 'schreibt...',
    contextTerm: 'Begriff im Kontext',
    discussWithAgent: 'Mit Agent besprechen',
    discussTermAria: (term: string) => `${term} mit dem Lernagenten besprechen`,
    initialAgentMessage: 'Hallo! Ich bin dein Lernbegleiter für diesen Case. Markierte Fachbegriffe starten direkt eine kontextbezogene Diskussion. Wo möchtest du einsteigen?',
    selfCheckTitle: 'Selbst-Check',
    selfCheckItems: [
      'Explizite Entscheidung oder These formuliert?',
      'Begründung mit konkreten Case-Fakten (Zahlen, Exhibits)?',
      'Konsequenz oder Trade-off benannt?',
    ],
    coverageTitle: 'Canvas-Bausteine im Entwurf',
    coverageAddressed: 'angesprochen',
    coverageMissing: 'noch nicht erkennbar',
    hintButton: 'Denkanstoß einholen',
    hintLoading: 'Denkanstoß wird geholt...',
    hintLabel: 'Denkanstoß',
    hintRemaining: (n: number) => `${n} verbleibend`,
    hintExhausted: 'Denkanstöße für diese Frage aufgebraucht — nutze den Lernchat.',
    hintError: 'Denkanstoß gerade nicht verfügbar — bitte gleich noch einmal versuchen.',
  },
  en: {
    loading: 'Loading...',
    taskMaterials: 'Task Materials',
    questions: 'Questions',
    teacherPreview: 'Teacher preview',
    exhibits: 'Exhibits',
    canvasEyebrow: 'Required analysis frame',
    canvasTitle: 'Business Model Canvas',
    canvasRequired: 'Required for this task',
    canvasIntro: 'Answer the questions using the Business Model Canvas. Structure your answer around the relevant canvas blocks and show how decision, risk, and impact affect Alpes Bank\'s business model.',
    canvasQuality: 'Strong answers do not just name terms; they apply the relevant canvas blocks concretely to the case. What matters is how clearly you explain the link between business model, competition, implementation, and risk.',
    answerRule: 'Write in complete sentences. Questions 1-2 require 50-200 words; questions 3-4 require 100-200 words.',
    points: 'pts',
    teacherAnswerRequirement: (min: number, max: number) => `Student answer requirement: ${min}-${max} words, complete sentences.`,
    answerPlaceholder: (min: number, max: number) => `Your answer in complete sentences (${min}-${max} words)...`,
    requirement: (min: number, max: number) => `Requirement: ${min}-${max} words, complete sentences`,
    words: (count: number) => `${count} words`,
    sentenceHint: 'Please use complete sentences.',
    invalidQuestion: (index: number, min: number, max: number) => `Question ${index + 1} must be between ${min} and ${max} words.`,
    evaluationError: 'The evaluation could not be completed.',
    evaluating: 'Evaluation is running. Please do not close this page.',
    submit: 'Submit & evaluate',
    submitting: 'Evaluating...',
    preview: 'Preview',
    industry: 'Industry',
    country: 'Country',
    sections: 'Sections',
    showQuestions: 'Show questions',
    learningChat: 'Learning chat',
    chatIntro: 'Highlighted terms start a focused discussion without losing your reading context.',
    activeTopic: 'Active topic',
    askAgent: 'Ask the agent about the material...',
    writing: 'is writing...',
    contextTerm: 'Term in context',
    discussWithAgent: 'Discuss with agent',
    discussTermAria: (term: string) => `Discuss ${term} with the learning agent`,
    initialAgentMessage: 'Hi. I am your learning companion for this case. Highlighted terms start a context-specific discussion. Where would you like to begin?',
    selfCheckTitle: 'Self-check',
    selfCheckItems: [
      'Explicit decision or thesis stated?',
      'Justified with concrete case facts (numbers, exhibits)?',
      'Consequence or trade-off named?',
    ],
    coverageTitle: 'Canvas blocks in your draft',
    coverageAddressed: 'addressed',
    coverageMissing: 'not yet visible',
    hintButton: 'Get a thinking prompt',
    hintLoading: 'Getting prompt...',
    hintLabel: 'Thinking prompt',
    hintRemaining: (n: number) => `${n} remaining`,
    hintExhausted: 'No prompts left for this question — use the learning chat.',
    hintError: 'Prompt unavailable right now — please try again shortly.',
  },
}

const CASE_GLOSSARY: Record<string, GlossaryTerm[]> = {
  'alpes-bank-genai-001': [
    {
      term: 'Wertschöpfungskette',
      explanation: 'Beschreibt die zusammenhängenden Aktivitäten, mit denen ein Unternehmen über mehrere Schritte hinweg Wert für Kundinnen und Kunden erzeugt.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Wertschöpfungskette" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Silos',
      explanation: 'Organisatorische Abschottungen zwischen Bereichen, die Informationsfluss, Zusammenarbeit und gemeinsame Verantwortung erschweren.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Silos" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Governance-Modell',
      explanation: 'Legt fest, wer entscheidet, wer kontrolliert und nach welchen Regeln Technologie verantwortungsvoll betrieben wird.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Governance-Modell" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Kontrollinstanz',
      explanation: 'Eine Rolle oder Person, die Ergebnisse prüft, Fehler abfängt und Verantwortung für die Qualität übernimmt.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Kontrollinstanz" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Rollout',
      explanation: 'Die schrittweise Einführung eines Systems im realen Betrieb, oft mit klar definiertem Umfang und Risikobegrenzung.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Rollout" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'Anwendungsfall',
      explanation: 'Ein klar umrissener Einsatzbereich, in dem Technologie ein konkretes Problem lösen oder Nutzen stiften soll.',
      starterPrompt: 'Erkläre mir kurz den Begriff "Anwendungsfall" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
    {
      term: 'MVP',
      explanation: 'Ein minimal funktionsfähiges Produkt, das den Kernnutzen schnell testbar macht, ohne schon vollständig ausgereift zu sein.',
      starterPrompt: 'Erkläre mir kurz den Begriff "MVP" und ordne in einem Satz ein, welche Rolle er in diesem Case spielt.',
    },
  ],
  'alpes-bank-genai-001-en': [
    {
      term: 'value chain',
      explanation: 'Describes the connected activities through which a company creates value for customers across several steps.',
      starterPrompt: 'Briefly explain the term "value chain" and state in one sentence what role it plays in this case.',
    },
    {
      term: 'silos',
      explanation: 'Organizational separations between units that make information flow, collaboration, and shared responsibility harder.',
      starterPrompt: 'Briefly explain the term "silos" and state in one sentence what role it plays in this case.',
    },
    {
      term: 'governance model',
      explanation: 'Defines who decides, who controls, and under which rules technology is operated responsibly.',
      starterPrompt: 'Briefly explain the term "governance model" and state in one sentence what role it plays in this case.',
    },
    {
      term: 'control point',
      explanation: 'A role or person who checks outputs, catches errors, and takes responsibility for quality.',
      starterPrompt: 'Briefly explain the term "control point" and state in one sentence what role it plays in this case.',
    },
    {
      term: 'rollout',
      explanation: 'The gradual introduction of a system into real operations, often with a defined scope and risk limits.',
      starterPrompt: 'Briefly explain the term "rollout" and state in one sentence what role it plays in this case.',
    },
    {
      term: 'use case',
      explanation: 'A clearly defined area of application in which technology should solve a concrete problem or create value.',
      starterPrompt: 'Briefly explain the term "use case" and state in one sentence what role it plays in this case.',
    },
    {
      term: 'MVP',
      explanation: 'A minimum viable product that makes the core value testable quickly without being fully mature yet.',
      starterPrompt: 'Briefly explain the term "MVP" and state in one sentence what role it plays in this case.',
    },
  ],
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function splitParagraphs(content: string) {
  return content.split(/\n\s*\n/).filter(Boolean)
}

function buildGlossaryMatcher(terms: GlossaryTerm[]) {
  if (!terms.length) return null
  const sortedTerms = [...terms].sort((a, b) => b.term.length - a.term.length)
  return new RegExp(`(${sortedTerms.map(({ term }) => escapeRegExp(term)).join('|')})`, 'gi')
}

function glossaryHighlightKey(sectionId: string, paragraphIndex: number, partIndex: number) {
  return `${sectionId}:${paragraphIndex}:${partIndex}`
}

function buildGlossaryHighlightTargets(
  sections: CaseSection[],
  glossaryMap: Map<string, GlossaryTerm>,
  glossaryPattern: RegExp | null,
): GlossaryHighlightTargets {
  const targets: GlossaryHighlightTargets = new Map()
  if (!glossaryPattern) return targets

  sections.forEach(section => {
    splitParagraphs(section.content).forEach((paragraph, paragraphIndex) => {
      paragraph.split(glossaryPattern).filter(Boolean).forEach((part, partIndex) => {
        const match = glossaryMap.get(part.toLowerCase())
        if (!match) return

        const normalizedTerm = match.term.toLowerCase()
        if (!targets.has(normalizedTerm)) {
          targets.set(normalizedTerm, glossaryHighlightKey(section.section_id, paragraphIndex, partIndex))
        }
      })
    })
  })

  return targets
}

// Case-Paket-Wortlimits haben Vorrang; Index-Fallback erhält das
// Verhalten des Alpes-Bank-Cases (dessen Fragen keine Limits tragen).
function questionRequirement(question: CaseQuestion, questionIndex: number): AnswerRequirement {
  if (question.min_words && question.max_words) {
    return { minWords: question.min_words, maxWords: question.max_words }
  }
  return getAnswerRequirement(questionIndex)
}

function getAnswerRequirement(questionIndex: number): AnswerRequirement {
  if (questionIndex <= 1) return { minWords: 50, maxWords: 200 }
  if (questionIndex <= 3) return { minWords: 100, maxWords: 200 }
  return { minWords: 150, maxWords: 200 }
}

function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

function readExperimentContext(): ExperimentContext | null {
  if (typeof window === 'undefined') return null

  try {
    return JSON.parse(sessionStorage.getItem('experiment_context') ?? 'null')
  } catch {
    return null
  }
}

function readClientIdentity(language: Locale): ClientIdentity {
  const participantId = sessionStorage.getItem('matrikelnummer') ?? ''
  const userId = sessionStorage.getItem('user_id') ?? (participantId ? `prolific_${participantId}` : 'u_anon')
  const storedExperiment = readExperimentContext()
  const experiment = storedExperiment
    ? {
      ...storedExperiment,
      metadata: {
        ...(storedExperiment.metadata ?? {}),
        language,
      },
    }
    : (participantId
    ? {
      provider: 'prolific',
      experiment_name: 'prolific_experimental_run',
      run_id: participantId,
      prolific_pid: participantId,
      metadata: { language },
    }
    : null)

  return { userId, participantId, experiment }
}

function messageFromError(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function hasSentenceStructure(text: string): boolean {
  return /[.!?]/.test(text.trim())
}

// Icon je Exhibit-Position (Exhibit 1 → Rechner, 2 → Chart-Lupe, 3 → Warnung).
// Dateien liegen als public/icons/*.svg (Vectorly, siehe public/icons/README.md);
// Einbettung über NotionIcon wie alle anderen Icons. Weitere Exhibits: kein Icon.
const EXHIBIT_ICONS = ['calculator', 'chart-magnifier', 'warning']

// Icon je Story-Abschnitt (nach section_id, sprachstabil über DE/EN). Gibt den
// sonst reinen Fließtext-Überschriften visuelle Orientierung. Der erste
// Abschnitt (Case-Einleitung) bekommt kein Icon, sondern Titel-Formatierung.
const SECTION_ICONS: Record<string, string> = {
  s2: 'hand-gesture',    // Der Auftrag: Generative AI beweisen
  s3: 'watch-clock',     // Die Umsetzung: Zwischen Tempo und Kontrolle
  s4: 'receipt-paper',   // Governance: Wer trägt die Verantwortung?
  s5: 'target-arrow',    // Ein Jahr später: Wachstum und seine Grenzen
}

function parseExhibitTable(content: string): ParsedExhibitTable | null {
  const lines = content
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)

  const pipeLines = lines.filter(line => line.includes('|'))
  if (pipeLines.length < 2) return null

  const parseRow = (line: string) =>
    line
      .split('|')
      .map(cell => cell.trim())
      .filter(Boolean)

  const headers = parseRow(pipeLines[0])
  if (headers.length < 2) return null

  const rows = pipeLines.slice(1)
    .map(parseRow)
    .filter(row => row.length >= 2)

  if (!rows.length) return null

  const notes = lines.filter(line => !line.includes('|'))

  return { headers, rows, notes }
}

function ExhibitTable({ content }: { content: string }) {
  const parsed = parseExhibitTable(content)

  if (!parsed) {
    return (
      <pre
        className="overflow-x-auto whitespace-pre-wrap text-xs leading-6"
        style={{ fontFamily: 'inherit' }}
      >
        {content}
      </pre>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              {parsed.headers.map((header, index) => (
                <th
                  key={`${header}-${index}`}
                  className="border-b px-4 py-3 text-left text-xs font-semibold tracking-[0.08em] uppercase"
                  style={{
                    borderColor: 'var(--hairline)',
                    color: 'var(--muted)',
                    whiteSpace: index === 0 ? 'normal' : 'nowrap',
                  }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {parsed.rows.map((row, rowIndex) => (
              <tr key={`row-${rowIndex}`}>
                {parsed.headers.map((_, cellIndex) => (
                  <td
                    key={`cell-${rowIndex}-${cellIndex}`}
                    className="border-b px-4 py-3 align-top text-sm"
                    style={{
                      borderColor: 'var(--hairline)',
                      color: 'var(--ink)',
                      fontWeight: cellIndex === 0 ? 500 : 400,
                      whiteSpace: cellIndex === 0 ? 'normal' : 'nowrap',
                    }}
                  >
                    {row[cellIndex] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {parsed.notes.map((note, index) => (
        <p key={`note-${index}`} className="text-sm leading-7" style={{ color: 'var(--ink)' }}>
          {note}
        </p>
      ))}
    </div>
  )
}

// Baut den Canvas-Guide aus dem Case-Paket (Union der pro Frage geforderten
// Bausteine, Erwartung als Hinweis). Der kuratierte Alpes-Bank-Case behält
// seine handgeschriebenen Hinweise (Hardcode-Fallback).
function deriveCanvasBlocks(caseData: Case | null, id: string, language: Locale): CanvasBlock[] {
  const fallback = BUSINESS_MODEL_CANVAS_BLOCKS[language]
  if (!caseData || id.startsWith('alpes-bank-genai-001')) return fallback
  const seen = new Map<string, CanvasBlock>()
  caseData.questions.forEach(q => (q.required_canvas_blocks ?? []).forEach(b => {
    if (b.block && !seen.has(b.block)) {
      seen.set(b.block, { key: b.block, label: b.label || b.block, hint: b.expectation || '' })
    }
  }))
  return seen.size > 0 ? Array.from(seen.values()) : fallback
}

function BusinessModelCanvasGuide({ language, blocks }: { language: Locale; blocks: CanvasBlock[] }) {
  const text = CASE_PAGE_TEXT[language]

  return (
    <section
      className="rounded-[28px] border p-6"
      style={{
        background: 'linear-gradient(135deg, rgba(21,99,61,0.09), rgba(184,134,11,0.08))',
        borderColor: 'var(--hairline)',
      }}
    >
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="mb-2 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
            {text.canvasEyebrow}
          </p>
          <h2 className="font-display text-2xl leading-tight flex items-center gap-3">
            <NotionIcon name="canvas" size={30} />
            {text.canvasTitle}
          </h2>
        </div>
        <span
          className="shrink-0 rounded-full px-3 py-1 text-xs font-medium tracking-wide"
          style={{ background: 'rgba(21,99,61,0.14)', color: 'var(--accent)' }}
        >
          {text.canvasRequired}
        </span>
      </div>

      <p className="mb-5 text-sm leading-7" style={{ color: 'var(--ink)' }}>
        {text.canvasIntro}
      </p>

      <div className="mb-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {blocks.map(block => (
          <div
            key={block.key}
            className="rounded-2xl px-4 py-4"
            style={{ background: 'rgba(250,250,248,0.72)', border: '1px solid var(--hairline)' }}
          >
            <p className="mb-2 text-xs font-semibold tracking-[0.08em] uppercase" style={{ color: 'var(--accent)' }}>
              {block.label}
            </p>
            <p className="text-sm leading-6" style={{ color: 'var(--ink)' }}>
              {block.hint}
            </p>
          </div>
        ))}
      </div>

      <div
        className="rounded-2xl px-4 py-4 text-sm leading-7"
        style={{ background: 'rgba(53,40,30,0.05)', color: 'var(--ink)' }}
      >
        {text.canvasQuality}
      </div>
    </section>
  )
}

function RichText({
  text,
  sectionId,
  paragraphIndex,
  glossaryMap,
  glossaryPattern,
  highlightTargets,
  activeTerm,
  onDiscuss,
  language,
}: {
  text: string
  sectionId: string
  paragraphIndex: number
  glossaryMap: Map<string, GlossaryTerm>
  glossaryPattern: RegExp | null
  highlightTargets: GlossaryHighlightTargets
  activeTerm: string | null
  onDiscuss: (term: GlossaryTerm) => void
  language: Locale
}) {
  if (!glossaryPattern) return text

  return text.split(glossaryPattern).filter(Boolean).map((part, index) => {
    const match = glossaryMap.get(part.toLowerCase())
    if (!match) return <Fragment key={`${part}-${index}`}>{part}</Fragment>
    if (highlightTargets.get(match.term.toLowerCase()) !== glossaryHighlightKey(sectionId, paragraphIndex, index)) {
      return <Fragment key={`${match.term}-plain-${index}`}>{part}</Fragment>
    }

    return (
      <GlossaryChip
        key={`${match.term}-${index}`}
        term={match}
        active={activeTerm === match.term}
        onDiscuss={onDiscuss}
        language={language}
      />
    )
  })
}

function GlossaryChip({
  term,
  active,
  onDiscuss,
  language,
}: {
  term: GlossaryTerm
  active: boolean
  onDiscuss: (term: GlossaryTerm) => void
  language: Locale
}) {
  const [open, setOpen] = useState(false)
  const text = CASE_PAGE_TEXT[language]

  return (
    <span
      className="relative inline-flex align-baseline"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        onClick={() => onDiscuss(term)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="mx-0.5 inline-flex items-center rounded-[4px] px-1.5 py-0.5 text-left text-[0.95em] font-medium transition-colors"
        style={active
          ? { background: 'var(--accent)', color: 'var(--white)' }
          : { background: 'rgba(21,99,61,0.14)', color: 'var(--accent)' }}
        aria-label={text.discussTermAria(term.term)}
      >
        {term.term}
      </button>

      <span
        className={clsx(
          'pointer-events-none absolute left-0 top-full z-20 mt-2 w-72 origin-top-left rounded-xl border px-4 py-3 text-sm shadow-sm transition-all duration-150',
          open ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0',
        )}
        style={{
          background: 'var(--white)',
          borderColor: 'var(--hairline)',
          color: 'var(--ink)',
        }}
        role="tooltip"
      >
        <span className="mb-2 flex items-start gap-2">
          <MessageSquare size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--accent)' }} />
          <span>
            <span className="text-xs font-semibold tracking-[0.12em] uppercase" style={{ color: 'var(--muted)' }}>
              {text.contextTerm}
            </span>
            <span className="mt-1 block text-sm leading-6">{term.explanation}</span>
          </span>
        </span>

        <button
          type="button"
          onMouseDown={e => e.preventDefault()}
          onClick={() => onDiscuss(term)}
          className="pointer-events-auto mt-1 inline-flex items-center gap-2 text-xs font-medium tracking-wide"
          style={{ color: 'var(--accent)' }}
        >
          <BookOpenText size={14} />
          {text.discussWithAgent}
        </button>
      </span>
    </span>
  )
}

interface TypingStats {
  typed: number
  pasted: number
  pasteCount: number
  largestPaste: number
  editMs: number
  lastEditAt: number | null
}

// Tipp-Fluss-Telemetrie (nur Aggregate, keine Inhalte). Läuft ausschließlich
// im onChange-Event-Handler — bewusst außerhalb der Komponente definiert.
function trackInputStats(
  statsMap: Record<string, TypingStats>,
  pasteMap: Record<string, number>,
  qid: string,
  previous: string,
  next: string,
): void {
  const stats = statsMap[qid] ?? {
    typed: 0, pasted: 0, pasteCount: 0, largestPaste: 0, editMs: 0, lastEditAt: null,
  }
  const delta = next.length - previous.length
  const pastedNow = pasteMap[qid] ?? 0
  if (pastedNow > 0 && delta > 0) {
    const pasteLen = Math.min(delta, pastedNow)
    stats.pasted += pasteLen
    stats.pasteCount += 1
    stats.largestPaste = Math.max(stats.largestPaste, pasteLen)
    stats.typed += Math.max(0, delta - pasteLen)
  } else if (delta > 0) {
    stats.typed += delta
  }
  pasteMap[qid] = 0
  const now = Date.now()
  if (stats.lastEditAt !== null && now - stats.lastEditAt < 60_000) {
    stats.editMs += now - stats.lastEditAt
  }
  stats.lastEditAt = now
  statsMap[qid] = stats
}

export default function CasePage() {
  const { id } = useParams<{ id: string }>()
  const path = usePathname()
  const router = useRouter()
  const [storedLanguage, setLanguage] = useLanguage()
  const [isTeacherMode, setIsTeacherMode] = useState(() => readTeacherMode())
  const [caseData, setCase] = useState<Case | null>(null)
  const language = isLocale(caseData?.language)
    ? caseData.language
    : id.endsWith('-en')
      ? languageFromCaseId(id)
      : storedLanguage
  const text = CASE_PAGE_TEXT[language]
  const [tab, setTab] = useState<'case' | 'questions'>('case')
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submissionId, setSubmissionId] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [chat, setChat] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState('')
  const [sending, setSending] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [activeTerm, setActiveTerm] = useState<string | null>(null)
  const [submissionError, setSubmissionError] = useState<string | null>(null)
  const [coverage, setCoverage] = useState<Record<string, { block: string; label: string; addressed: boolean }[]>>({})
  const [selfCheck, setSelfCheck] = useState<Record<string, boolean[]>>({})
  const [hints, setHints] = useState<Record<string, { text?: string; remaining: number; loading: boolean; error?: string }>>({})
  // Tipp-Fluss-Telemetrie: nur Aggregate (Zeichen, Paste-Events, Zeit) —
  // niemals Inhalte. Integritäts-Hinweis für Tutor:innen, kein Beweis.
  const typingStatsRef = useRef<Record<string, { typed: number; pasted: number; pasteCount: number; largestPaste: number; editMs: number; lastEditAt: number | null }>>({})
  const pendingPasteRef = useRef<Record<string, number>>({})
  const chatScrollRef = useRef<HTMLDivElement>(null)
  const historyRef = useRef<{ role: string; content: string }[]>([])
  const startedExperimentCaseRef = useRef<string | null>(null)
  const clientIdentity = useMemo(() => {
    if (typeof window === 'undefined' || isTeacherMode) return null
    return readClientIdentity(language)
  }, [isTeacherMode, language])

  useEffect(() => {
    if (storedLanguage !== language) {
      setLanguage(language)
    }
  }, [language, setLanguage, storedLanguage])

  useEffect(() => {
    const syncTeacherMode = () => setIsTeacherMode(readTeacherMode())
    window.addEventListener(APP_MODE_CHANGED_EVENT, syncTeacherMode)
    window.addEventListener('focus', syncTeacherMode)
    window.addEventListener('pageshow', syncTeacherMode)

    return () => {
      window.removeEventListener(APP_MODE_CHANGED_EVENT, syncTeacherMode)
      window.removeEventListener('focus', syncTeacherMode)
      window.removeEventListener('pageshow', syncTeacherMode)
    }
  }, [])

  useEffect(() => {
    void Promise.resolve().then(() => setIsTeacherMode(readTeacherMode()))
  }, [path])

  useEffect(() => {
    if (isTeacherMode) {
      sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'teacher')
      return
    }

    clearCookie('teacher_mode')
    sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'student')
  }, [isTeacherMode])

  useEffect(() => {
    apiFetch<Case>(`/admin/cases/${id}`).then(setCase)
  }, [id])

  useEffect(() => {
    if (isTeacherMode || !id || !caseData || !clientIdentity || startedExperimentCaseRef.current === id) return
    startedExperimentCaseRef.current = id
    void Promise.resolve().then(() => {
      setAnswers({})
      setSubmissionId(null)
      setSessionId(null)
      setChat([])
      setChatInput('')
      setActiveTerm(null)
      setSubmissionError(null)
      historyRef.current = []
    })

    const groupCode = sessionStorage.getItem('group_code') ?? undefined
    // target_tp: Case-Vorgabe; bei full-Cases (target_tp=0) die aktuelle
    // Phase aus dem TP_SCHEDULE (Fallback 1, falls Endpoint nicht erreichbar).
    const resolveTargetTp = async (): Promise<number> =>
      caseData.target_tp
      || (await apiFetch<{ current_tp: number }>('/tp').then(r => r.current_tp).catch(() => 1))

    void resolveTargetTp().then(targetTp => apiFetch<{ submission_id: string }>('/submissions', {
      method: 'POST',
      body: JSON.stringify({
        user_id: clientIdentity.userId,
        matrikelnummer: clientIdentity.participantId,
        group_code: groupCode,
        case_id: id,
        target_tp: targetTp,
        experiment: clientIdentity.experiment,
      }),
    })).then(r => setSubmissionId(r.submission_id))

    apiFetch<{ session_id: string }>('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        user_id: clientIdentity.userId,
        group_code: groupCode,
        case_id: id,
        experiment: clientIdentity.experiment,
      }),
    }).then(r => {
      setSessionId(r.session_id)
      historyRef.current = []
      setChat([{ role: 'agent', content: text.initialAgentMessage, agent_type: 'metacognitive' }])
    }).catch(console.error)
  }, [caseData, clientIdentity, id, isTeacherMode, text.initialAgentMessage])

  useEffect(() => {
    const node = chatScrollRef.current
    if (!node) return
    node.scrollTo({ top: node.scrollHeight, behavior: 'smooth' })
  }, [chat, sending])

  // Glossar: kuratierter Frontend-Hardcode (Alpes-Bank) hat Vorrang;
  // neue Cases bringen ihr Glossar im Case-Paket mit.
  const glossaryTerms = useMemo(() => {
    if (isTeacherMode) return []
    const hardcoded = CASE_GLOSSARY[id]
    if (hardcoded) return hardcoded
    return (caseData?.glossary ?? [])
      .filter(g => g.term)
      .map(g => ({ term: g.term, explanation: g.explanation, starterPrompt: g.starter_prompt }))
  }, [id, isTeacherMode, caseData?.glossary])
  const glossaryMap = useMemo(
    () => new Map(glossaryTerms.map(term => [term.term.toLowerCase(), term])),
    [glossaryTerms],
  )
  const glossaryPattern = useMemo(() => buildGlossaryMatcher(glossaryTerms), [glossaryTerms])
  const glossaryHighlightTargets = useMemo(
    () => buildGlossaryHighlightTargets(caseData?.sections ?? [], glossaryMap, glossaryPattern),
    [caseData?.sections, glossaryMap, glossaryPattern],
  )

  const sendChatMessage = async (content: string) => {
    if (!content.trim() || !sessionId || sending) return false

    const message = content.trim()
    setSending(true)
    setChatInput('')
    setChat(current => [...current, { role: 'user', content: message }])
    historyRef.current = [...historyRef.current, { role: 'user', content: message }]

    try {
      const res = await apiFetch<{ agent_type: string; content: string }>(
        `/sessions/${sessionId}/chat`,
        { method: 'POST', body: JSON.stringify({ content: message, history: historyRef.current.slice(-10) }) },
      )
      historyRef.current = [...historyRef.current, { role: 'assistant', content: res.content }]
      setChat(current => [...current, { role: 'agent', content: res.content, agent_type: res.agent_type }])
      return true
    } catch (error: unknown) {
      const messageText = messageFromError(error, language === 'en' ? 'Unknown error' : 'Unbekannter Fehler')
      setChat(current => [
        ...current,
        { role: 'agent', content: `${language === 'en' ? 'Error' : 'Fehler'}: ${messageText}`, agent_type: 'metacognitive' },
      ])
      return false
    } finally {
      setSending(false)
    }
  }

  const sendChat = async () => {
    await sendChatMessage(chatInput)
  }

  const startGlossaryChat = async (term: GlossaryTerm) => {
    setActiveTerm(term.term)

    if (!sessionId || sending) {
      setChatInput(term.starterPrompt)
      return
    }

    await sendChatMessage(term.starterPrompt)
  }

  const HINTS_PER_QUESTION = 2

  const trackInput = (qid: string, previous: string, next: string) => {
    trackInputStats(typingStatsRef.current, pendingPasteRef.current, qid, previous, next)
  }

  const saveAnswer = async (qid: string, text: string) => {
    if (!submissionId) return
    const stats = typingStatsRef.current[qid]
    await apiFetch(`/submissions/${submissionId}/answer`, {
      method: 'POST',
      body: JSON.stringify({
        question_id: qid,
        answer_text: text,
        stats: stats ? {
          typed_chars: stats.typed,
          pasted_chars: stats.pasted,
          paste_count: stats.pasteCount,
          largest_paste: stats.largestPaste,
          edit_seconds: Math.round(stats.editMs / 100) / 10,
        } : undefined,
      }),
    })
  }

  const fetchCoverage = async (qid: string, draft: string) => {
    if (!submissionId || !draft.trim()) return
    try {
      const res = await apiFetch<{ blocks: { block: string; label: string; addressed: boolean }[] }>(
        `/submissions/${submissionId}/questions/${qid}/coverage`,
        { method: 'POST', body: JSON.stringify({ answer_text: draft }) },
      )
      setCoverage(current => ({ ...current, [qid]: res.blocks }))
    } catch {
      // Coverage ist ein Komfort-Feature — Fehler still ignorieren.
    }
  }

  const requestHint = async (qid: string) => {
    const draft = answers[qid] ?? ''
    const current = hints[qid] ?? { remaining: HINTS_PER_QUESTION, loading: false }
    if (!submissionId || current.loading || current.remaining <= 0 || !draft.trim()) return
    setHints(h => ({ ...h, [qid]: { ...current, loading: true, error: undefined } }))
    try {
      const res = await apiFetch<{ feedback: string; remaining: number }>(
        `/submissions/${submissionId}/questions/${qid}/feedback`,
        { method: 'POST', body: JSON.stringify({ answer_text: draft }) },
      )
      setHints(h => ({ ...h, [qid]: { text: res.feedback, remaining: res.remaining, loading: false } }))
    } catch (error: unknown) {
      const message = messageFromError(error, text.hintError)
      const exhausted = /limit/i.test(message)
      setHints(h => ({
        ...h,
        [qid]: {
          ...current,
          loading: false,
          remaining: exhausted ? 0 : current.remaining,
          error: exhausted ? text.hintExhausted : text.hintError,
        },
      }))
    }
  }

  const handleSubmit = async () => {
    if (!submissionId || !caseData || submitting) return
    const invalidQuestion = caseData.questions.find((question, index) => {
      const requirement = questionRequirement(question, index)
      const wordCount = countWords(answers[question.question_id] ?? '')
      return wordCount < requirement.minWords || wordCount > requirement.maxWords
    })

    if (invalidQuestion) {
      const questionIndex = caseData.questions.findIndex(q => q.question_id === invalidQuestion.question_id)
      const requirement = questionRequirement(invalidQuestion, questionIndex)
      setSubmissionError(
        text.invalidQuestion(questionIndex, requirement.minWords, requirement.maxWords),
      )
      return
    }

    setSubmissionError(null)
    setSubmitting(true)

    try {
      await Promise.all(caseData.questions.map(question =>
        saveAnswer(question.question_id, answers[question.question_id] ?? ''),
      ))
      const result = await apiFetch<unknown>(`/submissions/${submissionId}/submit`, { method: 'POST' })
      sessionStorage.setItem(`result_${submissionId}`, JSON.stringify(result))
      // Echte Prolific-Läufe (STUDY_ID in der URL) brauchen den Completion-
      // Code auf /goodbye; alle anderen sehen ihr formatives Ergebnis.
      const isProlificRun = Boolean(clientIdentity?.experiment?.prolific_study_id)
      router.replace(isProlificRun ? '/goodbye' : `/results/${submissionId}`)
    } catch (error: unknown) {
      setSubmissionError(messageFromError(error, text.evaluationError))
    } finally {
      setSubmitting(false)
    }
  }

  if (!caseData) {
    return (
      <>
        <Nav />
        <main className="px-8 pt-32 text-sm" style={{ color: 'var(--muted)' }}>{text.loading}</main>
      </>
    )
  }

  const tabs = [
    { key: 'case' as const, label: text.taskMaterials, icon: <FileText size={14} /> },
    { key: 'questions' as const, label: text.questions, icon: <FileText size={14} /> },
  ]

  return (
    <>
      <Nav />
      <main className="mx-auto max-w-[1400px] px-6 pb-12 pt-24 lg:px-8">
        <div className="py-6">
          <p className="mb-1 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
            {isTeacherMode ? text.teacherPreview : `${caseData.industry} · ${caseData.country}`}
          </p>
          <h1 className="font-display text-3xl leading-tight">{caseData.title}</h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--muted)' }}>{caseData.tagline}</p>
        </div>

        <div className="divider" />

        <div className="flex gap-0 border-b" style={{ borderColor: 'var(--hairline)' }}>
          {tabs.map(t => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={clsx(
                'flex items-center gap-2 border-b-2 -mb-px px-5 py-3 text-xs font-medium tracking-wide transition-all',
                tab === t.key ? 'border-[var(--accent)]' : 'border-transparent',
              )}
              style={{ color: tab === t.key ? 'var(--accent)' : 'var(--muted)' }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        <div className="mt-8 grid items-start gap-8 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <section className="min-w-0">
            {tab === 'case' && (
              <div className="flex flex-col gap-10 pr-0 xl:pr-4">
                {caseData.sections.map((section, sectionIndex) => (
                  <section key={section.section_id}>
                    {sectionIndex === 0 ? (
                      <h2 className="mb-3 font-display text-2xl leading-tight">{section.title}</h2>
                    ) : (
                      <h2 className="mb-3 flex items-center gap-3 text-base font-medium">
                        {SECTION_ICONS[section.section_id] && (
                          <NotionIcon name={SECTION_ICONS[section.section_id]} size={30} className="shrink-0" />
                        )}
                        {section.title}
                      </h2>
                    )}
                    <div className="flex flex-col gap-5 text-sm leading-8">
                      {splitParagraphs(section.content).map((paragraph, index) => (
                        <div key={`${section.section_id}-${index}`}>
                          <RichText
                            text={paragraph}
                            sectionId={section.section_id}
                            paragraphIndex={index}
                            glossaryMap={glossaryMap}
                            glossaryPattern={glossaryPattern}
                            highlightTargets={glossaryHighlightTargets}
                            activeTerm={activeTerm}
                            onDiscuss={startGlossaryChat}
                            language={language}
                          />
                        </div>
                      ))}
                    </div>
                  </section>
                ))}

                {caseData.exhibits.length > 0 && (
                  <section>
                    <h2 className="mb-5 text-base font-medium">{text.exhibits}</h2>
                    <div className="flex flex-col gap-6">
                      {caseData.exhibits.map((exhibit, exhibitIndex) => (
                        <div
                          key={exhibit.exhibit_id}
                          className="rounded-2xl p-5"
                          style={{ border: '1px solid var(--hairline)', background: 'rgba(250,250,248,0.45)' }}
                        >
                          <div className="mb-3 flex items-center gap-2.5">
                            {EXHIBIT_ICONS[exhibitIndex] && (
                              <NotionIcon name={EXHIBIT_ICONS[exhibitIndex]} size={30} className="shrink-0" />
                            )}
                            <p className="text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
                              {exhibit.title}
                            </p>
                          </div>
                          {exhibit.exhibit_type === 'table'
                            ? <ExhibitTable content={exhibit.content} />
                            : (
                              <pre
                                className="overflow-x-auto whitespace-pre-wrap text-xs leading-6"
                                style={{ fontFamily: 'inherit' }}
                              >
                                {exhibit.content}
                              </pre>
                            )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            )}

            {tab === 'questions' && (
              <div className="flex max-w-3xl flex-col gap-8 pr-0 xl:pr-4">
                <BusinessModelCanvasGuide language={language} blocks={deriveCanvasBlocks(caseData, id, language)} />

                {!isTeacherMode && (
                  <div
                    className="rounded-2xl px-5 py-4 text-sm leading-7"
                    style={{ background: 'rgba(21,99,61,0.08)', color: 'var(--ink)' }}
                  >
                    {text.answerRule}
                  </div>
                )}

                {caseData.questions.map((question, index) => (
                  <div key={question.question_id}>
                    {(() => {
                      const requirement = questionRequirement(question, index)
                      const answerText = answers[question.question_id] ?? ''
                      const wordCount = countWords(answerText)
                      const isWithinRange = wordCount >= requirement.minWords && wordCount <= requirement.maxWords
                      const sentenceHintVisible = answerText.trim().length > 0 && !hasSentenceStructure(answerText)

                      return (
                        <>
                    <div className="mb-3 flex items-start justify-between gap-4">
                      <div className="flex items-start gap-4">
                        <span className="mt-0.5 shrink-0 font-mono text-xs" style={{ color: 'var(--muted)' }}>
                          {String(index + 1).padStart(2, '0')}
                        </span>
                        <p className="text-sm leading-6">{question.text}</p>
                      </div>
                      <span
                        className="shrink-0 rounded-full px-2.5 py-1 text-xs"
                        style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                      >
                        {question.max_points} {text.points}
                      </span>
                    </div>

                    {isTeacherMode ? (
                      <div
                        className="ml-8 rounded-2xl px-4 py-3 text-xs leading-6"
                        style={{ border: '1px solid var(--hairline)', color: 'var(--muted)' }}
                      >
                        {text.teacherAnswerRequirement(requirement.minWords, requirement.maxWords)}
                      </div>
                    ) : (
                      <>
                        <textarea
                          value={answerText}
                          onPaste={event => {
                            const pasted = event.clipboardData?.getData('text') ?? ''
                            pendingPasteRef.current[question.question_id] = pasted.length
                          }}
                          onChange={event => {
                            trackInput(question.question_id, answerText, event.target.value)
                            setAnswers(current => ({ ...current, [question.question_id]: event.target.value }))
                          }}
                          onBlur={event => {
                            saveAnswer(question.question_id, event.target.value)
                            fetchCoverage(question.question_id, event.target.value)
                          }}
                          rows={6}
                          placeholder={text.answerPlaceholder(requirement.minWords, requirement.maxWords)}
                          className="ml-8 w-full resize-none rounded-2xl bg-transparent px-4 py-3 text-sm outline-none transition-all"
                          style={{
                            border: `1px solid ${answerText.trim().length > 0 && !isWithinRange ? 'rgba(173,63,43,0.45)' : 'var(--hairline)'}`,
                            color: 'var(--ink)',
                          }}
                          onFocus={event => { event.currentTarget.style.borderColor = 'var(--accent)' }}
                          onBlurCapture={event => {
                            event.currentTarget.style.borderColor = answerText.trim().length > 0 && !isWithinRange
                              ? 'rgba(173,63,43,0.45)'
                              : 'var(--hairline)'
                          }}
                        />
                        <div className="ml-8 mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                          <span style={{ color: 'var(--muted)' }}>
                            {text.requirement(requirement.minWords, requirement.maxWords)}
                          </span>
                          <span style={{ color: answerText.trim().length === 0 || isWithinRange ? 'var(--accent)' : '#ad3f2b' }}>
                            {text.words(wordCount)}
                          </span>
                          {sentenceHintVisible && (
                            <span style={{ color: '#ad3f2b' }}>
                              {text.sentenceHint}
                            </span>
                          )}
                        </div>

                        {/* Canvas-Abdeckung (deterministisch, aktualisiert beim Verlassen des Felds) */}
                        {(coverage[question.question_id]?.length ?? 0) > 0 && (
                          <div className="ml-8 mt-3 flex flex-wrap items-center gap-2 text-xs">
                            <span style={{ color: 'var(--muted)' }}>{text.coverageTitle}:</span>
                            {coverage[question.question_id].map(b => (
                              <span
                                key={b.block}
                                className="rounded-full px-2.5 py-1"
                                style={{
                                  background: b.addressed ? 'rgba(21,99,61,0.1)' : 'rgba(53,40,30,0.07)',
                                  color: b.addressed ? 'var(--accent)' : 'var(--muted)',
                                }}
                                title={b.addressed ? text.coverageAddressed : text.coverageMissing}
                              >
                                {b.addressed ? '✓' : '○'} {b.label}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Selbst-Check (metakognitiv, nur lokal) */}
                        <div className="ml-8 mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs" style={{ color: 'var(--muted)' }}>
                          <span>{text.selfCheckTitle}:</span>
                          {text.selfCheckItems.map((item, itemIndex) => {
                            const checks = selfCheck[question.question_id] ?? [false, false, false]
                            return (
                              <label key={itemIndex} className="flex cursor-pointer items-center gap-1.5">
                                <input
                                  type="checkbox"
                                  checked={checks[itemIndex]}
                                  onChange={() => setSelfCheck(current => {
                                    const next = [...(current[question.question_id] ?? [false, false, false])]
                                    next[itemIndex] = !next[itemIndex]
                                    return { ...current, [question.question_id]: next }
                                  })}
                                />
                                <span>{item}</span>
                              </label>
                            )
                          })}
                        </div>

                        {/* Denkanstoß (formativ, ohne Punkte, max. 2 pro Frage) */}
                        <div className="ml-8 mt-3">
                          {(() => {
                            const hint = hints[question.question_id] ?? { remaining: HINTS_PER_QUESTION, loading: false }
                            return (
                              <>
                                <div className="flex items-center gap-3 text-xs">
                                  <button
                                    type="button"
                                    onClick={() => requestHint(question.question_id)}
                                    disabled={hint.loading || hint.remaining <= 0 || !answerText.trim()}
                                    className="rounded-full px-3 py-1.5 font-medium transition-all"
                                    style={{
                                      border: '1px solid rgba(53,40,30,0.25)',
                                      color: hint.remaining > 0 && answerText.trim() ? 'var(--ink)' : 'var(--muted)',
                                      opacity: hint.loading ? 0.6 : 1,
                                    }}
                                  >
                                    <NotionIcon name="idea" size={16} className="mr-1.5" />
                                    {hint.loading ? text.hintLoading : text.hintButton}
                                  </button>
                                  <span style={{ color: 'var(--muted)' }}>{text.hintRemaining(hint.remaining)}</span>
                                </div>
                                {hint.error && (
                                  <p className="mt-2 text-xs" style={{ color: '#ad3f2b' }}>{hint.error}</p>
                                )}
                                {hint.text && (
                                  <div
                                    className="mt-2 rounded-2xl px-4 py-3 text-xs leading-6"
                                    style={{ background: 'rgba(21,99,61,0.06)', color: 'var(--ink)' }}
                                  >
                                    <span className="font-medium">{text.hintLabel}: </span>
                                    {hint.text}
                                  </div>
                                )}
                              </>
                            )
                          })()}
                        </div>
                      </>
                    )}
                        </>
                      )
                    })()}
                  </div>
                ))}

                {!isTeacherMode && <div className="divider" />}

                {!isTeacherMode && submissionError && (
                  <p className="text-sm" style={{ color: '#ad3f2b' }}>
                    {submissionError}
                  </p>
                )}

                {!isTeacherMode && submitting && (
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>
                    {text.evaluating}
                  </p>
                )}

                {!isTeacherMode && (
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={submitting}
                    className="self-start rounded-full px-6 py-3 text-sm font-medium tracking-wide transition-all duration-200"
                    style={{ background: submitting ? 'var(--muted)' : 'var(--ink)', color: 'var(--white)' }}
                    onMouseEnter={event => { if (!submitting) event.currentTarget.style.background = 'var(--accent)' }}
                    onMouseLeave={event => { if (!submitting) event.currentTarget.style.background = 'var(--ink)' }}
                  >
                    {submitting ? text.submitting : text.submit}
                  </button>
                )}
              </div>
            )}
          </section>

          <aside className="xl:sticky xl:top-28">
            {isTeacherMode ? (
              <div
                className="rounded-[28px] border p-6"
                style={{ background: 'rgba(250,250,248,0.7)', borderColor: 'var(--hairline)' }}
              >
                <p className="text-xs tracking-widest uppercase mb-4" style={{ color: 'var(--muted)' }}>
                  {text.preview}
                </p>
                <div className="flex flex-col gap-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span style={{ color: 'var(--muted)' }}>{text.industry}</span>
                    <span className="font-medium">{caseData.industry}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span style={{ color: 'var(--muted)' }}>{text.country}</span>
                    <span className="font-medium">{caseData.country}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span style={{ color: 'var(--muted)' }}>{text.sections}</span>
                    <span className="font-medium">{caseData.sections.length}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span style={{ color: 'var(--muted)' }}>{text.exhibits}</span>
                    <span className="font-medium">{caseData.exhibits.length}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span style={{ color: 'var(--muted)' }}>{text.questions}</span>
                    <span className="font-medium">{caseData.questions.length}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setTab('questions')}
                  className="mt-6 w-full rounded-full px-5 py-3 text-sm font-medium transition-all"
                  style={{ background: 'var(--ink)', color: 'var(--white)' }}
                  onMouseEnter={event => { event.currentTarget.style.background = 'var(--accent)' }}
                  onMouseLeave={event => { event.currentTarget.style.background = 'var(--ink)' }}
                >
                  {text.showQuestions}
                </button>
              </div>
            ) : (
            <div
              className="overflow-hidden rounded-[28px] border"
              style={{
                background: 'rgba(250,250,248,0.7)',
                borderColor: 'var(--hairline)',
                backdropFilter: 'blur(10px)',
              }}
            >
              <div className="border-b px-5 py-4" style={{ borderColor: 'var(--hairline)' }}>
                <div className="flex items-center gap-3">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-full"
                    style={{ background: 'rgba(21,99,61,0.12)', color: 'var(--accent)' }}
                  >
                    <MessageSquare size={18} />
                  </div>
                  <div>
                    <p className="flex items-center gap-2 text-sm font-medium">
                      <NotionIcon name="chat" size={24} />
                      {text.learningChat}
                    </p>
                  </div>
                </div>

                <p className="mt-3 text-sm leading-6" style={{ color: 'var(--muted)' }}>
                  {text.chatIntro}
                </p>

                {activeTerm && (
                  <div
                    className="mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs"
                    style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                  >
                    <BookOpenText size={13} />
                    {text.activeTopic}: {activeTerm}
                  </div>
                )}
              </div>

              <div className="flex h-[28rem] flex-col">
                <div ref={chatScrollRef} className="flex-1 overflow-y-auto px-5 py-4">
                  <div className="flex flex-col gap-4">
                    {chat.map((message, index) => (
                      <div key={index} className={clsx('flex', message.role === 'user' ? 'justify-end' : 'justify-start')}>
                        {message.role === 'agent' && (
                          <span className="mr-2 mt-2 shrink-0 text-xs font-medium" style={{ color: 'var(--accent)' }}>
                            {AGENT_LABEL[language][message.agent_type ?? ''] ?? 'Agent'}
                          </span>
                        )}

                        <div
                          className="max-w-[18rem] rounded-2xl px-4 py-3 text-sm leading-6"
                          style={message.role === 'user'
                            ? { background: 'var(--ink)', color: 'var(--white)' }
                            : { background: 'var(--surface)', color: 'var(--ink)', border: '1px solid var(--hairline)' }}
                        >
                          {message.content}
                        </div>
                      </div>
                    ))}

                    {sending && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs" style={{ color: 'var(--accent)' }}>Agent</span>
                        <span className="text-xs" style={{ color: 'var(--muted)' }}>{text.writing}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="border-t px-4 py-4" style={{ borderColor: 'var(--hairline)' }}>
                  <div className="flex items-stretch overflow-hidden rounded-full" style={{ border: '1px solid var(--hairline)' }}>
                    <input
                      value={chatInput}
                      onChange={event => setChatInput(event.target.value)}
                      onKeyDown={event => {
                        if (event.key === 'Enter' && !event.shiftKey) {
                          event.preventDefault()
                          void sendChat()
                        }
                      }}
                      placeholder={text.askAgent}
                      className="min-w-0 flex-1 bg-transparent px-4 py-3 text-sm outline-none"
                      style={{ color: 'var(--ink)' }}
                    />
                    <button
                      type="button"
                      onClick={() => void sendChat()}
                      disabled={sending}
                      className="px-4 py-3 transition-all duration-150"
                      style={{ background: sending ? 'var(--muted)' : 'var(--ink)', color: 'var(--white)' }}
                      onMouseEnter={event => { if (!sending) event.currentTarget.style.background = 'var(--accent)' }}
                      onMouseLeave={event => { if (!sending) event.currentTarget.style.background = 'var(--ink)' }}
                    >
                      <Send size={15} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
            )}
          </aside>
        </div>
      </main>
    </>
  )
}
