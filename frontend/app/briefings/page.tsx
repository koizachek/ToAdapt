'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Nav from '@/components/Nav'
import HelpHint from '@/components/HelpHint'
import { teacherFetch } from '@/lib/api'
import { APP_MODE_STORAGE_KEY, readTeacherMaster } from '@/lib/appMode'
import { useLanguage } from '@/lib/useLanguage'
import { ChevronDown, ChevronRight, Download, FileUp, Loader2 } from 'lucide-react'

// KI-Briefings für Übungsgruppenleitungen (ÜGL).
// - Jede ÜGL sieht die Briefings ihrer eigenen Übungsgruppe (Tutor-Kennung =
//   Übungsgruppe, z.B. UEG07) und lädt sie als DOCX herunter.
// - Der Master-Tutor lädt zusätzlich den Canvas-Export (ZIP mit PPTX/DOCX/PDF)
//   hoch — DIREKT ans Backend mit kurzlebigem Upload-Token, weil Vercel
//   Request-Bodies auf 4,5 MB begrenzt — und ordnet nicht erkannte Abgaben zu.
// Keine Punkte, keine Stufen: Das Briefing ist Vorbereitungsmaterial, keine Note.

const TPS = [1, 2, 3, 4, 5]

interface BausteinBriefing {
  kernposition: string
  tragende_argumente: string[]
  duenne_stellen: string[]
  einschaetzung: string
}

interface Formal {
  baustein1_chars?: number
  baustein1_max?: number
  baustein1_within_limit?: boolean
  baustein2_chars?: number
  baustein2_max?: number
  baustein2_within_limit?: boolean
  code_valid?: boolean
  filename_valid?: boolean
  template_detected?: boolean
  notes?: string[]
  full_sentences_hint?: string | null
}

interface BriefingRecord {
  briefing_id: string
  filename: string
  format: string
  target_tp: number
  ueg: string
  sg: number | null
  code: string | null
  status: string
  uploaded_at: string
  evaluation_status: string
  needs_human_review: boolean
  review_reason: string | null
  guardrail_hits: string[]
  formal: Formal
  briefing: Record<string, BausteinBriefing>
  feedback: Record<string, BausteinFeedback | string>
  feedback_status: string
  feedback_released: boolean
  feedback_available_from: string | null
  feedback_needs_human_review: boolean
  feedback_review_reason: string | null
}

interface BausteinFeedback {
  was_traegt: string
  was_bleibt_duenn: string
  naechster_schritt: string
}

interface OverviewRow {
  target_tp: number
  ueg: string
  briefed_count: number
  review_count: number
  missing_groups: number[]
  latest_uploaded_at: string | null
}

interface BatchStatus {
  batch_id: string
  target_tp: number
  status: string
  filename: string
  total: number
  processed: number
  briefed: number
  unassigned: number
  failed: number
  review: number
  started_at: string | null
  finished_at: string | null
  error: string | null
  stale: boolean
}

const TEXT = {
  de: {
    eyebrow: 'Übungsgruppenleitung',
    title: 'KI-Briefings',
    intro: 'Je Stammgruppe ein Briefing zur Vorbereitung des Touchpoints: Kernposition, tragende Argumente, dünne Stellen als Ansatz für Rückfragen und eine Einschätzung in Prosa. Keine Punkte, keine Musterlösung — jede Wahl ist zulässig, beurteilt wird nur, ob die Begründung trägt.',
    helpIntro: 'Die Briefings entstehen automatisch aus den Abgaben in Canvas. Die Wahl der Spannungslinie und der Rückfragen bleibt Ihre didaktische Entscheidung. Das Feedback an die Stammgruppen entsteht erst nach dem Termin.',
    tpLabel: 'Touchpoint',
    uegFilter: 'Übungsgruppe (Master)',
    uegPlaceholder: 'z.B. UEG07 — leer = alle',
    downloadAll: (ueg: string) => `Briefing-Dokument ${ueg} herunterladen (DOCX)`,
    downloadOne: 'DOCX',
    overview: (n: number, missing: number[]) =>
      `${n} von 8 Stammgruppen vorhanden` + (missing.length ? ` · fehlend: ${missing.map(m => `SG${m}`).join(', ')}` : ''),
    noUeg: 'Ihre Tutor-Kennung ist keiner Übungsgruppe zugeordnet (erwartet z.B. UEG07). Bitte an die Kursleitung wenden.',
    noData: 'Für diesen Touchpoint liegen noch keine Briefings vor.',
    statusOk: 'Briefing erstellt',
    statusReview: 'Bitte prüfen',
    statusFallback: 'Technischer Fallback — Abgabe direkt lesen',
    statusFailed: 'Datei nicht lesbar',
    statusNoContent: 'Kein Text in der Abgabe',
    formalChars: (b: number, n: number, max: number, ok: boolean) => `Folie ${b + 1}: ${n}/${max} Zeichen${ok ? '' : ' (über der Grenze)'}`,
    kernposition: 'Kernposition',
    argumente: 'Tragende Argumente',
    duenn: 'Dünne Stellen (Ansatz für Rückfragen)',
    einschaetzung: 'Einschätzung',
    none: '—',
    baustein: (n: number) => `Baustein ${n}`,
    // Master
    uploadTitle: 'Master-Upload: Canvas-Export',
    uploadIntro: 'ZIP mit allen Stammgruppen-Abgaben (PPTX aus der offiziellen Vorlage, ersatzweise DOCX/PDF). Die Datei geht direkt ans Backend; die Verarbeitung läuft im Hintergrund — die Seite darf geschlossen werden.',
    fileLabel: 'ZIP-Datei wählen',
    upload: 'Hochladen & Briefings erstellen',
    uploading: 'Upload läuft…',
    running: (p: number, t: number) => `Verarbeitung läuft: ${p} von ${t} Abgaben`,
    done: (b: BatchStatus) => `Fertig: ${b.briefed} Briefings · ${b.unassigned} ohne Zuordnung · ${b.failed} nicht lesbar · ${b.review} zur Prüfung`,
    stale: 'Batch ohne Fortschritt seit über 30 Minuten — vermutlich durch einen Neustart abgebrochen. Bitte erneut hochladen (neueste Abgabe je Stammgruppe gewinnt).',
    batches: 'Letzte Uploads',
    unassignedTitle: (n: number) => `Zuordnung offen (${n})`,
    unassignedHint: 'Bei diesen Abgaben wurde kein Code (TPn-UEGxx-SGy) erkannt. Übungsgruppe und Stammgruppe eintragen.',
    assign: 'Zuordnen',
    uegInput: 'UEG',
    sgInput: 'SG',
    errorGeneric: 'Upload fehlgeschlagen — bitte erneut versuchen.',
    helpUpload: 'Hochgeladene Dateien und Mitgliedernamen werden nie gespeichert — nur Briefing, Feedback, formale Vorprüfung und die interne Einstufung.',
    // Feedback
    feedbackZip: (ueg: string) => `Feedback ${ueg} für die Stammgruppen (ZIP, ein DOCX je Gruppe)`,
    feedbackOne: 'Feedback',
    feedbackLocked: (from: string) => `Feedback an die Stammgruppen ab ${from} — erst nach dem Termin.`,
    feedbackHelp: 'Das Feedback ist das zweite KI-Produkt: je Baustein was trägt, was bleibt dünn, nächster Schritt, dazu ein Ausblick auf den nächsten Touchpoint und die Klausur. Es wird erst nach dem Termin freigegeben, damit der Dialog im Touchpoint die Echtheitsprüfung bleibt. Sie geben es Ihren Stammgruppen weiter, zum Beispiel über Canvas.',
    downloadAllUegs: (n: number) => `Alle ${n} Übungsgruppen als ZIP (ein Briefing-Dokument je Übungsgruppe)`,
    feedbackAllUegs: (n: number) => `Feedback aller ${n} Übungsgruppen als ZIP`,
    feedbackTitle: 'Feedback an die Stammgruppe',
    fbTraegt: 'Was trägt',
    fbDuenn: 'Was bleibt dünn',
    fbSchritt: 'Nächster Schritt',
    fbAusblick: 'Ausblick',
    fbReview: 'Feedback bitte vor der Weitergabe prüfen',
  },
  en: {
    eyebrow: 'Tutorial group lead',
    title: 'AI briefings',
    intro: 'One briefing per home group to prepare the touchpoint: core position, supporting arguments, thin spots as prompts for follow-up questions, and a prose assessment. No points, no model solution — any choice is admissible; only the reasoning is judged.',
    helpIntro: 'Briefings are generated automatically from the Canvas submissions. Choosing the line of tension and the questions remains your didactic decision. Feedback to the home groups is created only after the session.',
    tpLabel: 'Touchpoint',
    uegFilter: 'Tutorial group (master)',
    uegPlaceholder: 'e.g. UEG07 — empty = all',
    downloadAll: (ueg: string) => `Download briefing document ${ueg} (DOCX)`,
    downloadOne: 'DOCX',
    overview: (n: number, missing: number[]) =>
      `${n} of 8 home groups present` + (missing.length ? ` · missing: ${missing.map(m => `SG${m}`).join(', ')}` : ''),
    noUeg: 'Your tutor ID is not mapped to a tutorial group (expected e.g. UEG07). Please contact the course lead.',
    noData: 'No briefings for this touchpoint yet.',
    statusOk: 'Briefing ready',
    statusReview: 'Please check',
    statusFallback: 'Technical fallback — read the submission directly',
    statusFailed: 'File unreadable',
    statusNoContent: 'No text in submission',
    formalChars: (b: number, n: number, max: number, ok: boolean) => `Slide ${b + 1}: ${n}/${max} characters${ok ? '' : ' (over limit)'}`,
    kernposition: 'Core position',
    argumente: 'Supporting arguments',
    duenn: 'Thin spots (prompts for follow-up questions)',
    einschaetzung: 'Assessment',
    none: '—',
    baustein: (n: number) => `Building block ${n}`,
    uploadTitle: 'Master upload: Canvas export',
    uploadIntro: 'ZIP with all home-group submissions (PPTX from the official template, or DOCX/PDF). The file goes directly to the backend; processing runs in the background — you may close this page.',
    fileLabel: 'Choose ZIP file',
    upload: 'Upload & create briefings',
    uploading: 'Uploading…',
    running: (p: number, t: number) => `Processing: ${p} of ${t} submissions`,
    done: (b: BatchStatus) => `Done: ${b.briefed} briefings · ${b.unassigned} unassigned · ${b.failed} unreadable · ${b.review} to check`,
    stale: 'Batch without progress for over 30 minutes — probably interrupted by a restart. Please upload again (latest submission per home group wins).',
    batches: 'Recent uploads',
    unassignedTitle: (n: number) => `Assignment pending (${n})`,
    unassignedHint: 'No code (TPn-UEGxx-SGy) was detected in these submissions. Enter tutorial group and home group.',
    assign: 'Assign',
    uegInput: 'UEG',
    sgInput: 'SG',
    errorGeneric: 'Upload failed — please try again.',
    helpUpload: 'Uploaded files and member names are never stored — only the briefing, the feedback, the formal pre-check and the internal rating.',
    feedbackZip: (ueg: string) => `Feedback ${ueg} for the home groups (ZIP, one DOCX per group)`,
    feedbackOne: 'Feedback',
    feedbackLocked: (from: string) => `Feedback for the home groups available from ${from} — only after the session.`,
    feedbackHelp: 'The feedback is the second AI product: per building block what holds, what stays thin, next step, plus an outlook on the next touchpoint and the exam. It is released only after the session so that the dialogue in the touchpoint remains the authenticity check. You pass it on to your home groups, e.g. via Canvas.',
    downloadAllUegs: (n: number) => `All ${n} tutorial groups as ZIP (one briefing document per group)`,
    feedbackAllUegs: (n: number) => `Feedback of all ${n} tutorial groups as ZIP`,
    feedbackTitle: 'Feedback for the home group',
    fbTraegt: 'What holds',
    fbDuenn: 'What stays thin',
    fbSchritt: 'Next step',
    fbAusblick: 'Outlook',
    fbReview: 'Please check the feedback before passing it on',
  },
}

const REVIEW_TONE = '#ad3f2b'

const fmtDate = (iso: string | null) => {
  if (!iso) return '–'
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}
const FAIL_TONE = '#c0392b'

export default function BriefingsPage() {
  const [language] = useLanguage()
  const text = TEXT[language]
  const [isMaster] = useState(() => readTeacherMaster())

  const [tp, setTp] = useState(1)
  const [uegFilter, setUegFilter] = useState('')
  const [records, setRecords] = useState<BriefingRecord[]>([])
  const [overview, setOverview] = useState<OverviewRow[]>([])
  const [loadError, setLoadError] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  // Master: Upload + Batches
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [activeBatch, setActiveBatch] = useState<BatchStatus | null>(null)
  const [batches, setBatches] = useState<BatchStatus[]>([])
  const [assignDrafts, setAssignDrafts] = useState<Record<string, { ueg: string; sg: string }>>({})
  const [assigning, setAssigning] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Promise-Ketten statt async/await: setState nur in Callbacks, nie
  // synchron im Effekt (react-hooks/set-state-in-effect).
  const load = useCallback(() => {
    const query = `?tp=${tp}` + (isMaster && uegFilter.trim() ? `&ueg=${encodeURIComponent(uegFilter.trim())}` : '')
    return Promise.all([
      teacherFetch<BriefingRecord[]>(`/briefings${query}`),
      teacherFetch<OverviewRow[]>(`/briefings/overview?tp=${tp}`),
      isMaster ? teacherFetch<BatchStatus[]>(`/briefings/batches?tp=${tp}`) : Promise.resolve([] as BatchStatus[]),
    ])
      .then(([list, rows, batchList]) => {
        setRecords(list)
        setOverview(rows)
        setBatches(batchList)
        setLoadError('')
      })
      .catch((e: unknown) => setLoadError(e instanceof Error ? e.message : 'API error'))
  }, [tp, uegFilter, isMaster])

  useEffect(() => {
    sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'teacher')
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Batch pollen, bis fertig/fehlgeschlagen/stale
  useEffect(() => {
    if (!activeBatch || activeBatch.status !== 'running' || activeBatch.stale) return
    const timer = setInterval(async () => {
      try {
        const status = await teacherFetch<BatchStatus>(`/briefings/batches/${activeBatch.batch_id}`)
        setActiveBatch(status)
        if (status.status !== 'running' || status.stale) load()
      } catch {
        /* nächster Tick */
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [activeBatch, load])

  const submitUpload = async () => {
    if (!file || uploading) return
    setUploading(true)
    setUploadError('')
    try {
      const tokenRes = await fetch('/api/teacher/upload-token', { method: 'POST', credentials: 'same-origin' })
      if (!tokenRes.ok) {
        const err = await tokenRes.json().catch(() => ({}))
        throw new Error(typeof err.detail === 'string' ? err.detail : text.errorGeneric)
      }
      const { token, upload_url } = (await tokenRes.json()) as { token: string; upload_url: string }
      const formData = new FormData()
      formData.append('file', file)
      formData.append('target_tp', String(tp))
      // Direkt ans Backend (CORS via ALLOWED_ORIGINS), nicht über den Proxy.
      const res = await fetch(upload_url, {
        method: 'POST',
        body: formData,
        headers: { 'X-Upload-Token': token },
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(typeof err.detail === 'string' ? err.detail : text.errorGeneric)
      }
      const batch = (await res.json()) as BatchStatus
      setActiveBatch(batch)
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      load()
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : text.errorGeneric)
    } finally {
      setUploading(false)
    }
  }

  const assign = async (id: string) => {
    const draft = assignDrafts[id]
    if (!draft?.ueg.trim() || !draft?.sg.trim() || assigning) return
    setAssigning(id)
    try {
      await teacherFetch(`/briefings/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify({ ueg: draft.ueg.trim(), sg: Number(draft.sg) }),
      })
      setAssignDrafts(current => ({ ...current, [id]: { ueg: '', sg: '' } }))
      load()
    } catch {
      /* bleibt offen */
    } finally {
      setAssigning(null)
    }
  }

  const statusOf = (r: BriefingRecord) => {
    if (r.status === 'extraction_failed') return { label: text.statusFailed, tone: FAIL_TONE }
    if (r.status === 'no_content') return { label: text.statusNoContent, tone: FAIL_TONE }
    if (r.evaluation_status === 'technical_fallback') return { label: text.statusFallback, tone: FAIL_TONE }
    if (r.needs_human_review) return { label: text.statusReview, tone: REVIEW_TONE }
    return { label: text.statusOk, tone: 'var(--accent)' }
  }

  const unassigned = records.filter(r => r.status !== 'extraction_failed' && !(r.ueg && r.sg))
  const assigned = records.filter(r => !unassigned.includes(r))
  const ownRow = !isMaster ? overview[0] : undefined
  const grouped = new Map<string, BriefingRecord[]>()
  for (const r of assigned) {
    const key = r.ueg || '—'
    grouped.set(key, [...(grouped.get(key) ?? []), r])
  }

  const renderBaustein = (n: number, b?: BausteinBriefing) => (
    <div key={n} className="mb-5">
      <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>{text.baustein(n)}</p>
      <p className="text-sm mb-2"><span className="font-medium">{text.kernposition}: </span>{b?.kernposition ?? text.none}</p>
      <p className="text-xs font-medium mb-1">{text.argumente}</p>
      <ul className="list-disc pl-5 text-sm mb-2">
        {(b?.tragende_argumente ?? []).length ? b!.tragende_argumente.map((a, i) => <li key={i}>{a}</li>) : <li style={{ color: 'var(--muted)' }}>{text.none}</li>}
      </ul>
      <p className="text-xs font-medium mb-1">{text.duenn}</p>
      <ul className="list-disc pl-5 text-sm mb-2">
        {(b?.duenne_stellen ?? []).length ? b!.duenne_stellen.map((a, i) => <li key={i}>{a}</li>) : <li style={{ color: 'var(--muted)' }}>{text.none}</li>}
      </ul>
      <p className="text-sm"><span className="font-medium">{text.einschaetzung}: </span>{b?.einschaetzung ?? text.none}</p>
    </div>
  )

  const renderRecord = (r: BriefingRecord, editable: boolean) => {
    const status = statusOf(r)
    const open = !!expanded[r.briefing_id]
    const f = r.formal ?? {}
    return (
      <div key={r.briefing_id}>
        <div className="flex flex-wrap items-center justify-between gap-3 py-4 px-2">
          <button
            type="button"
            className="flex items-center gap-3 flex-wrap min-w-0 text-left"
            onClick={() => setExpanded(c => ({ ...c, [r.briefing_id]: !open }))}
          >
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <span className="font-mono text-sm font-medium">{r.code ?? r.filename}</span>
            {r.code && <span className="font-mono text-xs" style={{ color: 'var(--muted)' }}>{r.filename}</span>}
            <span className="text-xs" style={{ color: status.tone }}>{status.label}</span>
            {f.baustein1_max != null && (
              <span className="text-xs" style={{ color: f.baustein1_within_limit === false ? REVIEW_TONE : 'var(--muted)' }}>
                {text.formalChars(1, f.baustein1_chars ?? 0, f.baustein1_max, f.baustein1_within_limit !== false)}
              </span>
            )}
            {f.baustein2_max != null && (
              <span className="text-xs" style={{ color: f.baustein2_within_limit === false ? REVIEW_TONE : 'var(--muted)' }}>
                {text.formalChars(2, f.baustein2_chars ?? 0, f.baustein2_max, f.baustein2_within_limit !== false)}
              </span>
            )}
          </button>
          <div className="flex items-center gap-3 shrink-0">
            {r.status === 'briefed' && (
              <a
                href={`/api/teacher/briefings/${encodeURIComponent(r.briefing_id)}/docx`}
                className="flex items-center gap-1 px-3 py-1 text-xs font-medium"
                style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}
              >
                <Download size={12} /> {text.downloadOne}
              </a>
            )}
            {r.status === 'briefed' && r.feedback_released && (
              <a
                href={`/api/teacher/briefings/${encodeURIComponent(r.briefing_id)}/feedback/docx`}
                className="flex items-center gap-1 px-3 py-1 text-xs font-medium"
                style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}
              >
                <Download size={12} /> {text.feedbackOne}
              </a>
            )}
            {editable && (
              <span className="flex items-center gap-2">
                <input
                  value={assignDrafts[r.briefing_id]?.ueg ?? ''}
                  onChange={e => setAssignDrafts(c => ({ ...c, [r.briefing_id]: { ueg: e.target.value, sg: c[r.briefing_id]?.sg ?? '' } }))}
                  placeholder={text.uegInput}
                  className="px-2 py-1 text-xs outline-none w-20"
                  style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}
                />
                <input
                  value={assignDrafts[r.briefing_id]?.sg ?? ''}
                  onChange={e => setAssignDrafts(c => ({ ...c, [r.briefing_id]: { ueg: c[r.briefing_id]?.ueg ?? '', sg: e.target.value } }))}
                  placeholder={text.sgInput}
                  className="px-2 py-1 text-xs outline-none w-12"
                  style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}
                />
                <button
                  type="button"
                  onClick={() => assign(r.briefing_id)}
                  disabled={assigning === r.briefing_id}
                  className="px-3 py-1 text-xs font-medium disabled:opacity-40"
                  style={{ background: 'var(--ink)', color: 'var(--white)' }}
                >
                  {text.assign}
                </button>
              </span>
            )}
          </div>
        </div>
        {open && (
          <div className="px-8 pb-6">
            {r.review_reason && <p className="text-xs mb-4" style={{ color: REVIEW_TONE }}>{r.review_reason}</p>}
            {(f.notes ?? []).length > 0 && <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{f.notes!.join(' ')}</p>}
            {f.full_sentences_hint && <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{f.full_sentences_hint}</p>}
            {r.status === 'briefed' && (
              <>
                {renderBaustein(1, r.briefing?.baustein1)}
                {renderBaustein(2, r.briefing?.baustein2)}
              </>
            )}
            {r.status === 'briefed' && r.feedback && r.feedback.baustein1 && (
              <div className="mt-6 p-4" style={{ background: 'var(--surface)', border: '1px solid var(--hairline)' }}>
                <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
                  {text.feedbackTitle}
                  {!r.feedback_released && ` · ${text.feedbackLocked(fmtDate(r.feedback_available_from))}`}
                </p>
                {r.feedback_needs_human_review && (
                  <p className="text-xs mb-3" style={{ color: REVIEW_TONE }}>{text.fbReview}{r.feedback_review_reason ? ` — ${r.feedback_review_reason}` : ''}</p>
                )}
                {[1, 2].map(n => {
                  const fb = r.feedback[`baustein${n}`] as BausteinFeedback | undefined
                  return (
                    <div key={n} className="mb-4">
                      <p className="text-xs font-medium mb-1">{text.baustein(n)}</p>
                      <p className="text-sm"><span className="font-medium">{text.fbTraegt}: </span>{fb?.was_traegt ?? text.none}</p>
                      <p className="text-sm"><span className="font-medium">{text.fbDuenn}: </span>{fb?.was_bleibt_duenn ?? text.none}</p>
                      <p className="text-sm"><span className="font-medium">{text.fbSchritt}: </span>{fb?.naechster_schritt ?? text.none}</p>
                    </div>
                  )
                })}
                <p className="text-sm"><span className="font-medium">{text.fbAusblick}: </span>{String(r.feedback.feed_forward ?? text.none)}</p>
              </div>
            )}
          </div>
        )}
        <div className="divider" />
      </div>
    )
  }

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-5xl mx-auto">
        <div className="mb-10">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.eyebrow}</p>
          <h1 className="font-display text-5xl leading-none flex items-center gap-4">
            <FileUp size={40} />
            {text.title}
          </h1>
        </div>
        <p className="text-sm max-w-3xl mb-8" style={{ color: 'var(--muted)' }}>
          {text.intro}
          <HelpHint text={text.helpIntro} />
        </p>

        {/* TP-Auswahl + Master-Filter */}
        <div className="flex flex-wrap items-end gap-8 mb-10">
          <div>
            <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.tpLabel}</p>
            <div className="flex items-center gap-1 p-1 w-fit" style={{ border: '1px solid var(--hairline)' }}>
              {TPS.map(n => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setTp(n)}
                  className="px-4 py-1.5 text-xs font-medium transition-colors"
                  style={{ background: tp === n ? 'var(--ink)' : 'transparent', color: tp === n ? 'var(--white)' : 'var(--ink)' }}
                  aria-pressed={tp === n}
                >
                  TP{n}
                </button>
              ))}
            </div>
          </div>
          {isMaster && (
            <div>
              <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.uegFilter}</p>
              <input
                value={uegFilter}
                onChange={e => setUegFilter(e.target.value)}
                placeholder={text.uegPlaceholder}
                className="px-3 py-1.5 text-sm outline-none w-56"
                style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}
              />
            </div>
          )}
        </div>

        {/* Master-Upload */}
        {isMaster && (
          <div className="p-6 mb-12 flex flex-col gap-5" style={{ background: 'var(--surface)', border: '1px solid var(--hairline)' }}>
            <div>
              <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>{text.uploadTitle}</p>
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                {text.uploadIntro}
                <HelpHint text={text.helpUpload} />
              </p>
            </div>
            <div>
              <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>{text.fileLabel}</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip,application/zip"
                onChange={e => setFile(e.target.files?.[0] ?? null)}
                className="text-sm"
              />
            </div>
            <div className="flex items-center gap-4 flex-wrap">
              <button
                type="button"
                onClick={submitUpload}
                disabled={!file || uploading}
                className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium disabled:opacity-40"
                style={{ background: 'var(--ink)', color: 'var(--white)' }}
              >
                {uploading && <Loader2 size={14} className="animate-spin" />}
                {uploading ? text.uploading : text.upload}
              </button>
              {uploadError && <span className="text-sm" style={{ color: FAIL_TONE }}>{uploadError}</span>}
              {activeBatch && activeBatch.status === 'running' && !activeBatch.stale && (
                <span className="flex items-center gap-2 text-sm" style={{ color: 'var(--accent)' }}>
                  <Loader2 size={14} className="animate-spin" />
                  {text.running(activeBatch.processed, activeBatch.total)}
                </span>
              )}
              {activeBatch && activeBatch.status === 'done' && (
                <span className="text-sm" style={{ color: 'var(--accent)' }}>{text.done(activeBatch)}</span>
              )}
              {activeBatch && (activeBatch.stale || activeBatch.status === 'failed') && (
                <span className="text-sm" style={{ color: FAIL_TONE }}>{activeBatch.error ?? text.stale}</span>
              )}
            </div>
            {batches.length > 0 && (
              <div>
                <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>{text.batches}</p>
                <ul className="text-xs flex flex-col gap-1" style={{ color: 'var(--muted)' }}>
                  {batches.slice(0, 5).map(b => (
                    <li key={b.batch_id} className="font-mono">
                      {b.started_at?.slice(0, 16).replace('T', ' ')} · {b.filename || b.batch_id.slice(0, 8)} · {b.status}
                      {b.stale ? ' (stale)' : ''} · {b.processed}/{b.total} · {text.done(b)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {loadError && <p className="text-sm mb-6" style={{ color: FAIL_TONE }}>{loadError}</p>}

        {/* ÜGL-Sicht: eigene Übungsgruppe */}
        {!isMaster && !ownRow && records.length === 0 && !loadError && (
          <p className="py-10 text-sm text-center" style={{ color: 'var(--muted)' }}>{text.noData}</p>
        )}

        {/* Zuordnung offen (Master) */}
        {isMaster && unassigned.length > 0 && (
          <div className="mb-12">
            <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>{text.unassignedTitle(unassigned.length)}</p>
            <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{text.unassignedHint}</p>
            <div className="divider" />
            {unassigned.map(r => renderRecord(r, true))}
          </div>
        )}

        {/* ÜGL mit mehreren Übungsgruppen: Sammel-Downloads */}
        {!isMaster && grouped.size > 1 && (
          <div className="flex flex-wrap items-center gap-3 mb-8">
            <a
              href={`/api/teacher/briefings/docx?tp=${tp}`}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium"
              style={{ background: 'var(--ink)', color: 'var(--white)' }}
            >
              <Download size={14} /> {text.downloadAllUegs(grouped.size)}
            </a>
            {assigned[0]?.feedback_released && (
              <a
                href={`/api/teacher/briefings/feedback/zip?tp=${tp}`}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium"
                style={{ border: '1px solid var(--ink)', color: 'var(--ink)' }}
              >
                <Download size={14} /> {text.feedbackAllUegs(grouped.size)}
              </a>
            )}
          </div>
        )}

        {/* Briefings je Übungsgruppe */}
        {[...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([ueg, items]) => {
          const row = overview.find(o => o.ueg === ueg)
          return (
            <div key={ueg} className="mb-12">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div>
                  <p className="text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>{ueg}</p>
                  {row && (
                    <p className="text-sm mt-1" style={{ color: row.missing_groups.length ? REVIEW_TONE : 'var(--muted)' }}>
                      {text.overview(row.briefed_count, row.missing_groups)}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <a
                    href={`/api/teacher/briefings/docx?tp=${tp}&ueg=${encodeURIComponent(ueg)}`}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium"
                    style={{ background: 'var(--ink)', color: 'var(--white)' }}
                  >
                    <Download size={14} /> {text.downloadAll(ueg)}
                  </a>
                  {items[0]?.feedback_released ? (
                    <a
                      href={`/api/teacher/briefings/feedback/zip?tp=${tp}&ueg=${encodeURIComponent(ueg)}`}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-medium"
                      style={{ border: '1px solid var(--ink)', color: 'var(--ink)' }}
                    >
                      <Download size={14} /> {text.feedbackZip(ueg)}
                    </a>
                  ) : (
                    <span className="text-xs" style={{ color: 'var(--muted)' }}>
                      {text.feedbackLocked(fmtDate(items[0]?.feedback_available_from ?? null))}
                      <HelpHint text={text.feedbackHelp} />
                    </span>
                  )}
                </div>
              </div>
              <div className="divider" />
              {items.sort((a, b) => (a.sg ?? 99) - (b.sg ?? 99)).map(r => renderRecord(r, false))}
            </div>
          )
        })}
      </main>
    </>
  )
}
