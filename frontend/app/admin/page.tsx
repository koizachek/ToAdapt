'use client'

import { useCallback, useEffect, useState } from 'react'
import Nav from '@/components/Nav'
import HelpHint from '@/components/HelpHint'
import NotionIcon from '@/components/NotionIcon'
import TeacherIntro from '@/components/TeacherIntro'
import { teacherFetch } from '@/lib/api'
import { TEACHER_GUIDE } from '@/lib/teacherGuide'
import { Plus, Check, X, ChevronDown, ChevronUp, RefreshCw, Save, ShieldCheck, Archive } from 'lucide-react'
import { APP_MODE_STORAGE_KEY } from '@/lib/appMode'
import { languageQuery, Locale } from '@/lib/i18n'
import { useLanguage } from '@/lib/useLanguage'

interface CaseSummary { case_id: string; title: string; industry: string; difficulty: string; status: string }
interface Section { section_id: string; title: string; content: string }
interface Exhibit { exhibit_id: string; title: string; content: string; exhibit_type: string }
interface CanvasBlockSpec {
  block: string; label: string; accepted_keywords: string[]; expectation: string; weight: number
}
interface Question {
  question_id: string; phase: number; bloom_level: number; text: string
  max_points: number; rubric_reference: string
  allowed_frameworks: string[]; forbidden_framework_names: string[]
  evaluation_focus: string[]
  required_canvas_blocks: CanvasBlockSpec[]
  calibration_notes: string[]
}
interface GlossaryTerm { term: string; explanation: string; starter_prompt: string }
interface AgentGuidance { case_summary: string; key_tensions: string[]; common_mistakes: string[] }
interface Case extends CaseSummary {
  country: string; tagline: string; revision: number; review_notes: string
  sections: Section[]
  exhibits: Exhibit[]
  questions: Question[]
  glossary: GlossaryTerm[]
  agent_guidance: AgentGuidance | null
}
interface ValidationIssue { level: string; code: string; message: string; location: string }
interface ValidationReport { ok: boolean; issues: ValidationIssue[] }
interface AdminForm {
  industry: string
  country: string
  target_tp: number
}

const INDUSTRIES = ['Mobility', 'HealthTech', 'Retail', 'Logistics', 'EdTech', 'FinTech', 'Hospitality', 'Manufacturing']
const COUNTRY_OPTIONS = [
  { value: 'Deutschland', de: 'Deutschland', en: 'Germany' },
  { value: 'Österreich', de: 'Österreich', en: 'Austria' },
  { value: 'Frankreich', de: 'Frankreich', en: 'France' },
  { value: 'Niederlande', de: 'Niederlande', en: 'Netherlands' },
  { value: 'Schweden', de: 'Schweden', en: 'Sweden' },
  { value: 'Polen', de: 'Polen', en: 'Poland' },
  { value: 'Spanien', de: 'Spanien', en: 'Spain' },
  { value: 'Italien', de: 'Italien', en: 'Italy' },
]
const TP_OPTIONS: Record<Locale, { value: number; label: string }[]> = {
  de: [{ value: 1, label: 'TP 1 - Analyse' }, { value: 2, label: 'TP 2 - Strategie' }, { value: 3, label: 'TP 3 - Umsetzung' }, { value: 4, label: 'TP 4 - Integration' }],
  en: [{ value: 1, label: 'TP 1 - Analysis' }, { value: 2, label: 'TP 2 - Strategy' }, { value: 3, label: 'TP 3 - Implementation' }, { value: 4, label: 'TP 4 - Integration' }],
}

const ADMIN_TEXT = {
  de: {
    eyebrow: 'Dozenten-Interface',
    title: 'Admin',
    generateHeading: 'Neuen Case generieren',
    industry: 'Branche',
    country: 'Land',
    targetTp: 'Ziel-TP',
    generating: 'Wird generiert...',
    generate: 'Case generieren',
    reviewer: 'Reviewer',
    reviewerPlaceholder: 'Ihr Name',
    reviewerFallback: 'Dozent',
    status: { draft: 'Entwurf', approved: 'Freigegeben', rejected: 'Abgelehnt', retired: 'Archiviert' },
    approve: 'Freigeben',
    reject: 'Ablehnen',
    retire: 'Aus Pool nehmen',
    archiveTitle: 'Case archivieren',
    archiveBody: 'Der Case wird aus dem Pool genommen und ist für Studierende nicht mehr sichtbar. Nur der Master-Tutor kann archivieren — bitte den Master-Code eingeben.',
    archivePassword: 'Master-Code',
    archiveConfirm: 'Archivieren',
    archiveCancel: 'Abbrechen',
    archiveWrong: 'Falscher Code — nur der Master-Tutor kann das.',
    restore: 'Wiederherstellen',
    restoreTitle: 'Case wiederherstellen',
    restoreBody: 'Der Case kommt zurück in den Pool und ist für Studierende wieder sichtbar. Nur der Master-Tutor kann das — bitte den Master-Code eingeben.',
    questions: 'Fragen',
    sections: 'Abschnitte',
    exhibits: 'Exhibits',
    points: 'Pkt',
    bloom: 'Bloom',
    tagline: 'Tagline',
    caseTitle: 'Titel',
    revision: 'Revision',
    save: 'Änderungen speichern',
    saving: 'Speichert...',
    saved: 'Gespeichert.',
    validate: 'Prüfen',
    validating: 'Prüft...',
    validationOk: 'Alle Checks bestanden.',
    validationBlocked: 'Freigabe blockiert — Fehler beheben oder bewusst übersteuern.',
    forceApprove: 'Trotz Fehlern freigeben',
    regenInstruction: 'Anweisung, z.B. „mehr Zahlen, kürzer“',
    regenerate: 'Regenerieren',
    regenerating: 'Regeneriert...',
    unsaved: 'Ungespeicherte Änderungen',
    error: 'Aktion fehlgeschlagen — bitte erneut versuchen.',
    glossaryTitle: 'Glossar (Begriffe müssen wörtlich im Case-Text vorkommen)',
    glossaryTerm: 'Begriff',
    glossaryExplanation: 'Erklärung',
    glossaryStarter: 'Chat-Starter-Prompt',
    addTerm: '+ Begriff',
    guidanceTitle: 'Agent-Guidance (Kontext für den Lernchat)',
    guidanceSummary: 'Case-Kurzfassung',
    guidanceTensions: 'Spannungsfelder (eines pro Zeile)',
    guidanceMistakes: 'Typische Denkfehler (einer pro Zeile)',
    rubricFocus: 'Prüfkriterien (eines pro Zeile)',
    calibrationNotes: 'Bewertungs-Anker für den Judge (einer pro Zeile — leer = generische Bloom-Anker)',
    canvasBlocks: 'Canvas-Bausteine',
    blockKeywords: 'Signal-Keywords (kommagetrennt)',
    blockExpectation: 'Erwartung an die Antwort',
    noBlocks: 'Keine Canvas-Bausteine — der Judge nutzt den Alpes-Bank-Datei-Fallback!',
    helpGenerator: 'Erstellt per KI einen vollständigen Case-Entwurf: Fallgeschichte, Exhibits, Fragen samt Bewertungskriterien, Glossar und Chat-Kontext. Der Entwurf ist ein Startpunkt — freigegeben wird erst nach Ihrer Kuratierung.',
    helpReviewer: 'Wird aus Ihrem Login vorbelegt und an Freigaben/Änderungen protokolliert — so bleibt nachvollziehbar, wer welchen Case verantwortet.',
    helpRubric: 'Diese Kriterien und Signal-Keywords steuern die automatische Bewertung: Die Keywords zeigen an, ob Studierende einen Pflicht-Baustein ansprechen; die Erwartung beschreibt, was eine gute Antwort dazu zeigen muss. Formulieren Sie pfadoffen — mehrere gute Antwortwege müssen volle Punkte erreichen können.',
    helpCalibration: 'Feinjustierung für die KI-Bewertung dieser Frage (z.B. „verlangt zwei klar getrennte Herausforderungen"). Leer lassen ist ok — dann gelten generische Anker je Denk-Niveau. Nach spürbaren Änderungen: Stichprobe von Antworten gegenlesen.',
    helpGlossary: 'Begriffe werden im Case-Text hervorgehoben und starten per Klick eine Erklärung im Lernchat. Wichtig: Jeder Begriff muss WÖRTLICH im Text vorkommen, sonst kann er nicht hervorgehoben werden (der Prüf-Check warnt).',
    helpGuidance: 'Kontext für den Lernbegleiter: Spannungsfelder und typische Denkfehler dieses Cases. Der Chat nutzt sie, um bessere Rückfragen zu stellen — er warnt nie direkt, sondern macht Fehler durch Fragen sichtbar.',
    helpApprove: 'Freigeben macht den Case für Studierende sichtbar. Vorher läuft ein automatischer Check: Regelverstöße (Modellnamen, reservierte Kurs-Cases) blockieren; Warnungen (fehlende Keywords, Glossar-Begriffe nicht im Text) sollten Sie beheben. Übersteuern ist möglich, wird aber protokolliert.',
  },
  en: {
    eyebrow: 'Teacher interface',
    title: 'Admin',
    generateHeading: 'Generate new case',
    industry: 'Industry',
    country: 'Country',
    targetTp: 'Target TP',
    generating: 'Generating...',
    generate: 'Generate case',
    reviewer: 'Reviewer',
    reviewerPlaceholder: 'Your name',
    reviewerFallback: 'Teacher',
    status: { draft: 'Draft', approved: 'Approved', rejected: 'Rejected', retired: 'Retired' },
    approve: 'Approve',
    reject: 'Reject',
    retire: 'Remove from pool',
    archiveTitle: 'Archive case',
    archiveBody: 'The case will be removed from the pool and is no longer visible to students. Only the master tutor can archive — enter the master code.',
    archivePassword: 'Master code',
    archiveConfirm: 'Archive',
    archiveCancel: 'Cancel',
    archiveWrong: 'Wrong code — only the master tutor can do this.',
    restore: 'Restore',
    restoreTitle: 'Restore case',
    restoreBody: 'The case returns to the pool and is visible to students again. Only the master tutor can do this — enter the master code.',
    questions: 'Questions',
    sections: 'Sections',
    exhibits: 'Exhibits',
    points: 'pts',
    bloom: 'Bloom',
    tagline: 'Tagline',
    caseTitle: 'Title',
    revision: 'Revision',
    save: 'Save changes',
    saving: 'Saving...',
    saved: 'Saved.',
    validate: 'Validate',
    validating: 'Validating...',
    validationOk: 'All checks passed.',
    validationBlocked: 'Approval blocked — fix the errors or deliberately override.',
    forceApprove: 'Approve despite errors',
    regenInstruction: 'Instruction, e.g. "more numbers, shorter"',
    regenerate: 'Regenerate',
    regenerating: 'Regenerating...',
    unsaved: 'Unsaved changes',
    error: 'Action failed — please try again.',
    glossaryTitle: 'Glossary (terms must appear verbatim in the case text)',
    glossaryTerm: 'Term',
    glossaryExplanation: 'Explanation',
    glossaryStarter: 'Chat starter prompt',
    addTerm: '+ term',
    guidanceTitle: 'Agent guidance (context for the learning chat)',
    guidanceSummary: 'Case summary',
    guidanceTensions: 'Key tensions (one per line)',
    guidanceMistakes: 'Common mistakes (one per line)',
    rubricFocus: 'Assessment criteria (one per line)',
    calibrationNotes: 'Judge calibration anchors (one per line — empty = generic Bloom anchors)',
    canvasBlocks: 'Canvas blocks',
    blockKeywords: 'Signal keywords (comma-separated)',
    blockExpectation: 'Expectation for the answer',
    noBlocks: 'No canvas blocks — the judge falls back to the Alpes-Bank file rubric!',
    helpGenerator: 'Uses AI to create a complete case draft: story, exhibits, questions with assessment criteria, glossary, and chat context. The draft is a starting point — it only goes live after your curation.',
    helpReviewer: 'Prefilled from your login and recorded with approvals/edits — so it stays traceable who owns which case.',
    helpRubric: 'These criteria and signal keywords drive the automatic grading: keywords indicate whether students address a required block; the expectation describes what a good answer must show. Phrase them path-open — several good answer paths must be able to reach full points.',
    helpCalibration: 'Fine-tuning for the AI grading of this question (e.g. "requires two clearly separated challenges"). Leaving it empty is fine — generic anchors per thinking level apply. After substantial changes: spot-check a sample of graded answers.',
    helpGlossary: 'Terms are highlighted in the case text and start an explanation in the learning chat when clicked. Important: each term must appear VERBATIM in the text, otherwise it cannot be highlighted (the validation check warns).',
    helpGuidance: 'Context for the learning companion: tensions and typical thinking errors of this case. The chat uses them to ask better questions — it never warns directly, but surfaces errors through questions.',
    helpApprove: 'Approving makes the case visible to students. An automatic check runs first: rule violations (framework names, reserved course cases) block; warnings (missing keywords, glossary terms not in text) should be fixed. Overriding is possible but logged.',
  },
}

const INPUT_STYLE = { border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' } as const
const STATUS_STYLE: Record<string, string> = {
  draft:    'rgba(53,40,30,0.12)',
  approved: 'rgba(21,99,61,0.15)',
  rejected: 'rgba(192,57,43,0.1)',
  retired:  'rgba(53,40,30,0.06)',
}

export default function AdminPage() {
  const [language] = useLanguage()
  const [cases, setCases]       = useState<CaseSummary[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [draft, setDraft]       = useState<Case | null>(null)
  const [dirty, setDirty]       = useState(false)
  const [generating, setGen]    = useState(false)
  const [busy, setBusy]         = useState<string | null>(null)  // 'save' | 'validate' | 'regen:<id>' | 'approve'
  const [notice, setNotice]     = useState('')
  const [report, setReport]     = useState<ValidationReport | null>(null)
  const [regenInstructions, setRegenInstructions] = useState<Record<string, string>>({})
  // Passwortgeschütztes Archivieren/Wiederherstellen (nur Master-Tutor).
  const [archiveTarget, setArchiveTarget] = useState<{ id: string; title: string; action: 'retire' | 'restore' } | null>(null)
  const [archivePassword, setArchivePassword] = useState('')
  const [archiveError, setArchiveError] = useState('')
  const [archiving, setArchiving] = useState(false)
  const [form, setForm]         = useState<AdminForm>({ industry: INDUSTRIES[0], country: COUNTRY_OPTIONS[0].value, target_tp: 1 })
  // Vorbelegt mit der Tutor-Kennung aus dem Login (teacher_name-Cookie, nur UI).
  const [reviewer, setReviewer] = useState(() => {
    if (typeof document === 'undefined') return ''
    const match = document.cookie.match(/(?:^|; )teacher_name=([^;]*)/)
    return match ? decodeURIComponent(match[1]) : ''
  })
  const text = ADMIN_TEXT[language]

  const load = useCallback(
    () => teacherFetch<CaseSummary[]>(`/admin/cases?${languageQuery(language)}`).then(setCases),
    [language],
  )

  useEffect(() => {
    sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'teacher')
    load()
  }, [load])

  const generate = async () => {
    setGen(true)
    const selectedCountry = COUNTRY_OPTIONS.find(country => country.value === form.country)
    const country = selectedCountry?.[language] ?? form.country
    try {
      await teacherFetch('/admin/cases/generate', {
        method: 'POST',
        body: JSON.stringify({ ...form, country, language, difficulty: `tp${form.target_tp}` }),
      })
      await load()
    } finally { setGen(false) }
  }

  const openEditor = async (id: string) => {
    if (expanded === id) { setExpanded(null); setDraft(null); setDirty(false); setReport(null); return }
    setExpanded(id)
    setReport(null)
    setDirty(false)
    const c = await teacherFetch<Case>(`/admin/cases/${id}`)
    setDraft(c)
  }

  const applyServerCase = (c: Case) => {
    setDraft(c)
    setDirty(false)
    load()
  }

  const updateDraft = (update: Partial<Case>) => {
    setDraft(d => (d ? { ...d, ...update } : d))
    setDirty(true)
    setNotice('')
  }

  const save = async () => {
    if (!draft) return
    setBusy('save')
    setNotice('')
    try {
      const c = await teacherFetch<Case>(`/admin/cases/${draft.case_id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          editor: reviewer || text.reviewerFallback,
          title: draft.title,
          tagline: draft.tagline,
          sections: draft.sections,
          exhibits: draft.exhibits,
          questions: draft.questions,
          glossary: draft.glossary,
          agent_guidance: draft.agent_guidance,
        }),
      })
      applyServerCase(c)
      setNotice(text.saved)
    } catch { setNotice(text.error) } finally { setBusy(null) }
  }

  const validate = async () => {
    if (!draft) return
    setBusy('validate')
    try {
      setReport(await teacherFetch<ValidationReport>(`/admin/cases/${draft.case_id}/validate`))
    } catch { setNotice(text.error) } finally { setBusy(null) }
  }

  const regenerate = async (target: string, targetId: string | null) => {
    if (!draft) return
    const key = `${target}:${targetId ?? ''}`
    setBusy(`regen:${key}`)
    setNotice('')
    try {
      const c = await teacherFetch<Case>(`/admin/cases/${draft.case_id}/regenerate`, {
        method: 'POST',
        body: JSON.stringify({
          editor: reviewer || text.reviewerFallback,
          target,
          target_id: targetId,
          instructions: regenInstructions[key] ?? '',
        }),
      })
      applyServerCase(c)
      setRegenInstructions(p => ({ ...p, [key]: '' }))
    } catch { setNotice(text.error) } finally { setBusy(null) }
  }

  const review = async (id: string, action: 'approve' | 'reject' | 'retire' | 'restore', force = false) => {
    setBusy('approve')
    setNotice('')
    try {
      const c = await teacherFetch<Case>(`/admin/cases/${id}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ reviewer: reviewer || text.reviewerFallback, force }),
      })
      setReport(null)
      if (expanded === id) applyServerCase(c)
      else load()
    } catch (err) {
      // 422 = Validierung blockiert die Freigabe → Report anzeigen
      const message = err instanceof Error ? err.message : ''
      try {
        const parsed = JSON.parse(message)
        if (parsed?.issues) { setReport({ ok: false, issues: parsed.issues }); return }
      } catch { /* kein JSON-Detail */ }
      setNotice(text.error)
    } finally { setBusy(null) }
  }

  // Archivieren erst nach Bestätigung des eigenen Passworts (serverseitig
  // gegen die Tutor-Zugangscodes geprüft), damit ein Case nicht versehentlich
  // unwiderruflich aus dem Pool verschwindet.
  const confirmArchive = async () => {
    if (!archiveTarget || archiving) return
    setArchiving(true)
    setArchiveError('')
    try {
      const res = await fetch('/api/verify-teacher', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ password: archivePassword }),
      })
      if (!res.ok) { setArchiveError(text.archiveWrong); return }
      await review(archiveTarget.id, archiveTarget.action)
      setArchiveTarget(null)
      setArchivePassword('')
    } catch {
      setArchiveError(text.error)
    } finally {
      setArchiving(false)
    }
  }

  const regenControl = (target: string, targetId: string | null) => {
    const key = `${target}:${targetId ?? ''}`
    const running = busy === `regen:${key}`
    return (
      <div className="flex items-center gap-2 mt-2">
        <input
          value={regenInstructions[key] ?? ''}
          onChange={e => setRegenInstructions(p => ({ ...p, [key]: e.target.value }))}
          placeholder={text.regenInstruction}
          className="flex-1 px-3 py-1.5 text-xs bg-transparent outline-none"
          style={INPUT_STYLE}
        />
        <button
          onClick={() => regenerate(target, targetId)}
          disabled={busy !== null}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all"
          style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)', opacity: busy && !running ? 0.5 : 1 }}
          title={text.regenerate}
        >
          <RefreshCw size={11} className={running ? 'animate-spin' : ''} />
          {running ? text.regenerating : text.regenerate}
        </button>
      </div>
    )
  }

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-4xl mx-auto">
        <div className="mb-12">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.eyebrow}</p>
          <h1 className="font-display text-5xl leading-none flex items-center gap-4">
            <NotionIcon name="admin" size={44} />
            {text.title}
          </h1>
        </div>

        <TeacherIntro
          storageKey="toadapt_intro_admin_v1"
          title={TEACHER_GUIDE[language].admin.title}
          steps={TEACHER_GUIDE[language].admin.steps}
          hint={TEACHER_GUIDE[language].hint}
          dismissLabel={TEACHER_GUIDE[language].dismissLabel}
        />

        <div className="divider mb-10" />

        {/* Generator form */}
        <section className="mb-14">
          <p className="flex items-center gap-2 text-xs tracking-widest uppercase mb-6" style={{ color: 'var(--muted)' }}>
            <NotionIcon name="generator" size={24} />
            {text.generateHeading}
            <HelpHint text={text.helpGenerator} />
          </p>
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { label: text.industry, key: 'industry' as const, options: INDUSTRIES.map(value => ({ value, label: value })) },
              { label: text.country, key: 'country' as const, options: COUNTRY_OPTIONS.map(country => ({ value: country.value, label: country[language] })) },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs mb-2 font-medium" style={{ color: 'var(--line)' }}>{f.label}</label>
                <select
                  value={form[f.key]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  className="w-full px-3 py-2.5 text-sm bg-transparent outline-none"
                  style={INPUT_STYLE}
                >
                  {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            ))}
            <div>
              <label className="block text-xs mb-2 font-medium" style={{ color: 'var(--line)' }}>{text.targetTp}</label>
              <select
                value={form.target_tp}
                onChange={e => setForm(p => ({ ...p, target_tp: Number(e.target.value) }))}
                className="w-full px-3 py-2.5 text-sm bg-transparent outline-none"
                style={INPUT_STYLE}
              >
                {TP_OPTIONS[language].map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <button
            onClick={generate}
            disabled={generating}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium tracking-wide transition-all duration-200"
            style={{ background: 'var(--ink)', color: 'var(--white)' }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'var(--ink)')}
          >
            <Plus size={14} />
            {generating ? text.generating : text.generate}
          </button>
        </section>

        {/* Reviewer name */}
        <div className="mb-8 flex items-center gap-4">
          <p className="text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>{text.reviewer}<HelpHint text={text.helpReviewer} /></p>
          <input
            value={reviewer}
            onChange={e => setReviewer(e.target.value)}
            placeholder={text.reviewerPlaceholder}
            className="px-3 py-1.5 text-sm bg-transparent outline-none"
            style={{ ...INPUT_STYLE, width: '180px' }}
          />
        </div>

        {/* Case list */}
        <div className="divider mb-6" />
        <ul className="flex flex-col">
          {cases.map((c, i) => (
            <li key={c.case_id}>
              {i > 0 && <div className="divider" />}
              <div className="py-5">
                <div className="flex items-center justify-between">
                  <button onClick={() => openEditor(c.case_id)} className="flex items-center gap-4 text-left flex-1 group">
                    <span className="text-xs font-mono" style={{ color: 'var(--muted)' }}>{String(i+1).padStart(2,'0')}</span>
                    <div>
                      <p className="text-sm font-medium group-hover:text-[var(--accent)] transition-colors">{c.title}</p>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>{c.industry}</p>
                    </div>
                    {expanded === c.case_id ? <ChevronUp size={14} style={{ color: 'var(--muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--muted)' }} />}
                  </button>
                  <div className="flex items-center gap-3">
                    <span className="text-xs px-2 py-0.5" style={{ background: STATUS_STYLE[c.status], color: 'var(--ink)' }}>
                      {text.status[c.status as keyof typeof text.status] ?? c.status}
                    </span>
                    {c.status === 'draft' && (
                      <>
                        <button
                          onClick={() => review(c.case_id, 'approve')}
                          className="p-1.5 transition-all"
                          style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                          title={text.approve}
                        ><Check size={13} /></button>
                        <button
                          onClick={() => review(c.case_id, 'reject')}
                          className="p-1.5 transition-all"
                          style={{ background: 'rgba(192,57,43,0.08)', color: '#c0392b' }}
                          title={text.reject}
                        ><X size={13} /></button>
                      </>
                    )}
                    {c.status === 'approved' && (
                      <button
                        onClick={() => { setArchiveTarget({ id: c.case_id, title: c.title, action: 'retire' }); setArchivePassword(''); setArchiveError('') }}
                        className="p-1.5 transition-all"
                        style={{ background: 'rgba(53,40,30,0.08)', color: 'var(--ink)' }}
                        title={text.retire}
                      ><Archive size={13} /></button>
                    )}
                    {c.status === 'retired' && (
                      <button
                        onClick={() => { setArchiveTarget({ id: c.case_id, title: c.title, action: 'restore' }); setArchivePassword(''); setArchiveError('') }}
                        className="p-1.5 transition-all"
                        style={{ background: 'rgba(21,99,61,0.1)', color: 'var(--accent)' }}
                        title={text.restore}
                      ><RefreshCw size={13} /></button>
                    )}
                  </div>
                </div>

                {/* Editor */}
                {expanded === c.case_id && draft && draft.case_id === c.case_id && (
                  <div className="mt-6 ml-10 flex flex-col gap-6">
                    <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--muted)' }}>
                      <span>{text.revision} {draft.revision}</span>
                      {dirty && <span style={{ color: '#ad3f2b' }}>{text.unsaved}</span>}
                      {notice && <span>{notice}</span>}
                    </div>

                    <div>
                      <label className="block text-xs mb-2 font-medium" style={{ color: 'var(--line)' }}>{text.caseTitle}</label>
                      <input
                        value={draft.title}
                        onChange={e => updateDraft({ title: e.target.value })}
                        className="w-full px-3 py-2 text-sm bg-transparent outline-none"
                        style={INPUT_STYLE}
                      />
                    </div>

                    <div>
                      <label className="block text-xs mb-2 font-medium" style={{ color: 'var(--line)' }}>{text.tagline}</label>
                      <textarea
                        value={draft.tagline}
                        onChange={e => updateDraft({ tagline: e.target.value })}
                        rows={2}
                        className="w-full px-3 py-2 text-sm bg-transparent outline-none resize-y"
                        style={INPUT_STYLE}
                      />
                      {regenControl('tagline', null)}
                    </div>

                    <div>
                      <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.sections}</p>
                      {draft.sections.map((s, si) => (
                        <div key={s.section_id} className="mb-5">
                          <input
                            value={s.title}
                            onChange={e => updateDraft({ sections: draft.sections.map((x, xi) => xi === si ? { ...x, title: e.target.value } : x) })}
                            className="w-full px-3 py-1.5 text-xs font-medium bg-transparent outline-none mb-1"
                            style={INPUT_STYLE}
                          />
                          <textarea
                            value={s.content}
                            onChange={e => updateDraft({ sections: draft.sections.map((x, xi) => xi === si ? { ...x, content: e.target.value } : x) })}
                            rows={5}
                            className="w-full px-3 py-2 text-xs leading-5 bg-transparent outline-none resize-y"
                            style={INPUT_STYLE}
                          />
                          {regenControl('section', s.section_id)}
                        </div>
                      ))}
                    </div>

                    <div>
                      <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.exhibits}</p>
                      {draft.exhibits.map((ex, xi) => (
                        <div key={ex.exhibit_id} className="mb-5">
                          <input
                            value={ex.title}
                            onChange={e => updateDraft({ exhibits: draft.exhibits.map((x, i2) => i2 === xi ? { ...x, title: e.target.value } : x) })}
                            className="w-full px-3 py-1.5 text-xs font-medium bg-transparent outline-none mb-1"
                            style={INPUT_STYLE}
                          />
                          <textarea
                            value={ex.content}
                            onChange={e => updateDraft({ exhibits: draft.exhibits.map((x, i2) => i2 === xi ? { ...x, content: e.target.value } : x) })}
                            rows={4}
                            className="w-full px-3 py-2 text-xs leading-5 font-mono bg-transparent outline-none resize-y"
                            style={INPUT_STYLE}
                          />
                          {regenControl('exhibit', ex.exhibit_id)}
                        </div>
                      ))}
                    </div>

                    <div>
                      <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.questions}</p>
                      {draft.questions.map((q, qi) => (
                        <div key={q.question_id} className="mb-5">
                          <textarea
                            value={q.text}
                            onChange={e => updateDraft({ questions: draft.questions.map((x, i2) => i2 === qi ? { ...x, text: e.target.value } : x) })}
                            rows={3}
                            className="w-full px-3 py-2 text-xs leading-5 bg-transparent outline-none resize-y"
                            style={INPUT_STYLE}
                          />
                          <div className="flex items-center gap-3 mt-1 text-xs" style={{ color: 'var(--muted)' }}>
                            <label className="flex items-center gap-1">
                              {text.points}
                              <input
                                type="number" min={1} max={30}
                                value={q.max_points}
                                onChange={e => updateDraft({ questions: draft.questions.map((x, i2) => i2 === qi ? { ...x, max_points: Number(e.target.value) } : x) })}
                                className="w-16 px-2 py-1 bg-transparent outline-none"
                                style={INPUT_STYLE}
                              />
                            </label>
                            <span>{text.bloom} {q.bloom_level}</span>
                          </div>

                          {/* Eingebettetes Bewertungspaket */}
                          <div className="mt-3 flex flex-col gap-2 pl-3" style={{ borderLeft: '2px solid var(--hairline)' }}>
                            <label className="text-xs font-medium" style={{ color: 'var(--line)' }}>{text.rubricFocus}<HelpHint text={text.helpRubric} /></label>
                            <textarea
                              value={(q.evaluation_focus ?? []).join('\n')}
                              onChange={e => updateDraft({ questions: draft.questions.map((x, i2) => i2 === qi ? { ...x, evaluation_focus: e.target.value.split('\n').filter(l => l.trim()) } : x) })}
                              rows={3}
                              className="w-full px-3 py-2 text-xs leading-5 bg-transparent outline-none resize-y"
                              style={INPUT_STYLE}
                            />

                            <label className="text-xs font-medium" style={{ color: 'var(--line)' }}>{text.canvasBlocks}</label>
                            {(q.required_canvas_blocks ?? []).length === 0 && (
                              <p className="text-xs" style={{ color: '#c0392b' }}>{text.noBlocks}</p>
                            )}
                            {(q.required_canvas_blocks ?? []).map((b, bi) => (
                              <div key={b.block || bi} className="flex flex-col gap-1 mb-1">
                                <p className="text-xs font-medium">{b.label || b.block}</p>
                                <input
                                  value={b.accepted_keywords.join(', ')}
                                  placeholder={text.blockKeywords}
                                  onChange={e => updateDraft({ questions: draft.questions.map((x, i2) => i2 === qi ? {
                                    ...x,
                                    required_canvas_blocks: x.required_canvas_blocks.map((y, yi) => yi === bi ? { ...y, accepted_keywords: e.target.value.split(',').map(k => k.trim()).filter(Boolean) } : y),
                                  } : x) })}
                                  className="w-full px-3 py-1.5 text-xs bg-transparent outline-none"
                                  style={INPUT_STYLE}
                                />
                                <input
                                  value={b.expectation}
                                  placeholder={text.blockExpectation}
                                  onChange={e => updateDraft({ questions: draft.questions.map((x, i2) => i2 === qi ? {
                                    ...x,
                                    required_canvas_blocks: x.required_canvas_blocks.map((y, yi) => yi === bi ? { ...y, expectation: e.target.value } : y),
                                  } : x) })}
                                  className="w-full px-3 py-1.5 text-xs bg-transparent outline-none"
                                  style={INPUT_STYLE}
                                />
                              </div>
                            ))}

                            <label className="text-xs font-medium" style={{ color: 'var(--line)' }}>{text.calibrationNotes}<HelpHint text={text.helpCalibration} /></label>
                            <textarea
                              value={(q.calibration_notes ?? []).join('\n')}
                              onChange={e => updateDraft({ questions: draft.questions.map((x, i2) => i2 === qi ? { ...x, calibration_notes: e.target.value.split('\n').filter(l => l.trim()) } : x) })}
                              rows={2}
                              className="w-full px-3 py-2 text-xs leading-5 bg-transparent outline-none resize-y"
                              style={INPUT_STYLE}
                            />
                          </div>
                          {regenControl('question', q.question_id)}
                        </div>
                      ))}
                    </div>

                    {/* Glossar */}
                    <div>
                      <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.glossaryTitle}<HelpHint text={text.helpGlossary} /></p>
                      {(draft.glossary ?? []).map((g, gi) => (
                        <div key={gi} className="mb-3 grid grid-cols-3 gap-2">
                          {([['term', text.glossaryTerm], ['explanation', text.glossaryExplanation], ['starter_prompt', text.glossaryStarter]] as const).map(([field, label]) => (
                            <input
                              key={field}
                              value={g[field]}
                              placeholder={label}
                              onChange={e => updateDraft({ glossary: draft.glossary.map((x, xi) => xi === gi ? { ...x, [field]: e.target.value } : x) })}
                              className="w-full px-3 py-1.5 text-xs bg-transparent outline-none"
                              style={INPUT_STYLE}
                            />
                          ))}
                        </div>
                      ))}
                      <button
                        onClick={() => updateDraft({ glossary: [...(draft.glossary ?? []), { term: '', explanation: '', starter_prompt: '' }] })}
                        className="px-3 py-1.5 text-xs font-medium"
                        style={{ border: '1px solid rgba(53,40,30,0.25)', color: 'var(--ink)' }}
                      >
                        {text.addTerm}
                      </button>
                    </div>

                    {/* Agent-Guidance */}
                    <div>
                      <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.guidanceTitle}<HelpHint text={text.helpGuidance} /></p>
                      <label className="block text-xs mb-1 font-medium" style={{ color: 'var(--line)' }}>{text.guidanceSummary}</label>
                      <textarea
                        value={draft.agent_guidance?.case_summary ?? ''}
                        onChange={e => updateDraft({ agent_guidance: { key_tensions: [], common_mistakes: [], ...(draft.agent_guidance ?? {}), case_summary: e.target.value } })}
                        rows={2}
                        className="w-full px-3 py-2 text-xs leading-5 bg-transparent outline-none resize-y mb-2"
                        style={INPUT_STYLE}
                      />
                      <label className="block text-xs mb-1 font-medium" style={{ color: 'var(--line)' }}>{text.guidanceTensions}</label>
                      <textarea
                        value={(draft.agent_guidance?.key_tensions ?? []).join('\n')}
                        onChange={e => updateDraft({ agent_guidance: { case_summary: '', common_mistakes: [], ...(draft.agent_guidance ?? {}), key_tensions: e.target.value.split('\n').filter(l => l.trim()) } })}
                        rows={3}
                        className="w-full px-3 py-2 text-xs leading-5 bg-transparent outline-none resize-y mb-2"
                        style={INPUT_STYLE}
                      />
                      <label className="block text-xs mb-1 font-medium" style={{ color: 'var(--line)' }}>{text.guidanceMistakes}</label>
                      <textarea
                        value={(draft.agent_guidance?.common_mistakes ?? []).join('\n')}
                        onChange={e => updateDraft({ agent_guidance: { case_summary: '', key_tensions: [], ...(draft.agent_guidance ?? {}), common_mistakes: e.target.value.split('\n').filter(l => l.trim()) } })}
                        rows={3}
                        className="w-full px-3 py-2 text-xs leading-5 bg-transparent outline-none resize-y"
                        style={INPUT_STYLE}
                      />
                    </div>

                    {/* Validation report */}
                    {report && (
                      <div className="p-4" style={{ background: report.ok ? 'rgba(21,99,61,0.07)' : 'rgba(192,57,43,0.06)', border: '1px solid var(--hairline)' }}>
                        <p className="text-xs font-medium mb-2">
                          {report.ok ? text.validationOk : text.validationBlocked}
                        </p>
                        {report.issues.map((issue, ii) => (
                          <p key={ii} className="text-xs leading-5" style={{ color: issue.level === 'error' ? '#c0392b' : 'var(--muted)' }}>
                            [{issue.level}] {issue.location && `${issue.location}: `}{issue.message}
                          </p>
                        ))}
                        {!report.ok && (
                          <button
                            onClick={() => review(draft.case_id, 'approve', true)}
                            disabled={busy !== null}
                            className="mt-3 px-3 py-1.5 text-xs font-medium"
                            style={{ border: '1px solid #c0392b', color: '#c0392b' }}
                          >
                            {text.forceApprove}
                          </button>
                        )}
                      </div>
                    )}

                    {/* Editor actions */}
                    <div className="flex items-center gap-3">
                      <button
                        onClick={save}
                        disabled={busy !== null || !dirty}
                        className="flex items-center gap-2 px-4 py-2 text-xs font-medium tracking-wide"
                        style={{ background: dirty ? 'var(--ink)' : 'rgba(53,40,30,0.25)', color: 'var(--white)' }}
                      >
                        <Save size={12} />
                        {busy === 'save' ? text.saving : text.save}
                      </button>
                      <button
                        onClick={validate}
                        disabled={busy !== null}
                        className="flex items-center gap-2 px-4 py-2 text-xs font-medium tracking-wide"
                        style={{ border: '1px solid rgba(53,40,30,0.3)', color: 'var(--ink)' }}
                      >
                        <ShieldCheck size={12} />
                        {busy === 'validate' ? text.validating : text.validate}
                      </button>
                      <HelpHint text={text.helpApprove} />
                      {draft.status === 'draft' && (
                        <button
                          onClick={() => review(draft.case_id, 'approve')}
                          disabled={busy !== null || dirty}
                          title={dirty ? text.unsaved : text.approve}
                          className="flex items-center gap-2 px-4 py-2 text-xs font-medium tracking-wide"
                          style={{ background: dirty ? 'rgba(21,99,61,0.25)' : 'var(--accent)', color: 'var(--white)' }}
                        >
                          <Check size={12} />
                          {text.approve}
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>

        {archiveTarget && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-6"
            style={{ background: 'rgba(26,26,26,0.4)' }}
            onClick={() => !archiving && setArchiveTarget(null)}
          >
            <form
              onClick={e => e.stopPropagation()}
              onSubmit={e => { e.preventDefault(); void confirmArchive() }}
              className="w-full max-w-sm rounded-2xl p-6"
              style={{ background: 'var(--surface)', border: '1px solid var(--hairline)' }}
            >
              <div className="mb-2 flex items-center gap-2">
                {archiveTarget.action === 'restore'
                  ? <RefreshCw size={16} style={{ color: 'var(--ink)' }} />
                  : <Archive size={16} style={{ color: 'var(--ink)' }} />}
                <h2 className="text-base font-medium">{archiveTarget.action === 'restore' ? text.restoreTitle : text.archiveTitle}</h2>
              </div>
              <p className="mb-1 text-sm font-medium">{archiveTarget.title}</p>
              <p className="mb-4 text-xs leading-6" style={{ color: 'var(--muted)' }}>{archiveTarget.action === 'restore' ? text.restoreBody : text.archiveBody}</p>
              <label className="mb-2 block text-xs font-medium" style={{ color: 'var(--line)' }}>{text.archivePassword}</label>
              <input
                type="password"
                autoFocus
                value={archivePassword}
                onChange={e => { setArchivePassword(e.target.value); setArchiveError('') }}
                className="w-full px-3 py-2 text-sm outline-none"
                style={INPUT_STYLE}
              />
              {archiveError && <p className="mt-2 text-xs" style={{ color: '#c0392b' }}>{archiveError}</p>}
              <div className="mt-5 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setArchiveTarget(null)}
                  disabled={archiving}
                  className="px-4 py-2 text-xs font-medium"
                  style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}
                >{text.archiveCancel}</button>
                <button
                  type="submit"
                  disabled={archiving || !archivePassword}
                  className="px-4 py-2 text-xs font-medium transition-all"
                  style={{ background: 'var(--ink)', color: 'var(--white)', opacity: archiving || !archivePassword ? 0.5 : 1 }}
                >{archiveTarget.action === 'restore' ? text.restore : text.archiveConfirm}</button>
              </div>
            </form>
          </div>
        )}
      </main>
    </>
  )
}
