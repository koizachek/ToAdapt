'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Nav from '@/components/Nav'
import HelpHint from '@/components/HelpHint'
import { teacherFetch } from '@/lib/api'
import { APP_MODE_STORAGE_KEY, readTeacherMaster } from '@/lib/appMode'
import { useLanguage } from '@/lib/useLanguage'
import { useClientValue } from '@/lib/useClientValue'
import { AlertTriangle, ChevronDown, ChevronRight, Download, FileUp, KeyRound, Loader2, Pencil } from 'lucide-react'

// KI-Briefings für Übungsgruppenleiter (Owner-Entscheidung 2026-09-13).
// - Jeder Übungsgruppenleiter lädt EINE ZIP-Datei mit den Einreichungen
//   seiner Gruppen hoch (direkt ans Backend mit kurzlebigem Upload-Token, weil
//   Vercel Request-Bodies auf 4,5 MB begrenzt). Touchpoint, Übungsgruppe und
//   Stammgruppe liest das System vom Deckblatt; er prüft oder korrigiert sie.
// - Er sieht nur, was er selbst hochgeladen hat, und lädt Briefings (Word) und
//   Feedbacks (ZIP je Touchpoint) herunter.
// - Der Master sieht zusätzlich das Monitoring: je Konto Uploads/Downloads je
//   Touchpoint und Gruppe, Passwort-Anfragen, Einmalcodes, dieselben Downloads.
// Keine Punkte, keine Stufen: Das Briefing ist Vorbereitungsmaterial, keine Note.

const TPS = [1, 2, 3, 4, 5]

interface BausteinBriefing {
  kernposition: string
  tragende_argumente: string[]
  duenne_stellen: string[]
  einschaetzung: string
}

interface Rueckfragen {
  zu_staerken: string[]
  zu_schwaechen: string[]
}

interface BausteinFeedback {
  was_traegt: string
  was_bleibt_duenn: string
  naechster_schritt: string
}

interface Formal {
  baustein1_chars?: number
  baustein1_max?: number
  baustein1_within_limit?: boolean
  baustein2_chars?: number
  baustein2_max?: number
  baustein2_within_limit?: boolean
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
  code_source: string | null
  status: string
  uploaded_at: string
  uploaded_by: string | null
  evaluation_status: string
  needs_human_review: boolean
  review_reason: string | null
  formal: Formal
  briefing: Record<string, BausteinBriefing | Rueckfragen>
  feedback: Record<string, BausteinFeedback | string>
  feedback_status: string
  feedback_needs_human_review: boolean
  feedback_review_reason: string | null
  reject_reason: string | null
  pii_removed: string[]
  injection_suspected: boolean
  injection_findings: string[]
}

interface BatchStatus {
  batch_id: string
  tps: number[]
  status: string
  filename: string
  total: number
  processed: number
  briefed: number
  unassigned: number
  failed: number
  rejected: number
  review: number
  uploaded_by: string | null
  started_at: string | null
  finished_at: string | null
  error: string | null
  stale: boolean
}

interface MonitoringGroup {
  briefing_id: string
  code: string | null
  ueg: string
  sg: number | null
  status: string
  needs_human_review: boolean
  injection_suspected: boolean
  reject_reason: string | null
  uploaded_at: string | null
  filename: string | null
}

interface MonitoringTp {
  target_tp: number
  count: number
  briefed: number
  review: number
  latest_uploaded_at: string | null
  last_download_briefing_at: string | null
  last_download_feedback_at: string | null
  groups: MonitoringGroup[]
}

interface MonitoringRow {
  account: string
  is_tutor_account: boolean
  is_master: boolean
  password_set: boolean | null
  password_set_at: string | null
  last_login_at: string | null
  reset_requested_at: string | null
  reset_code_active: boolean
  reset_code_expires_at: string | null
  upload_count: number
  review_open: number
  rejected: number
  injection_suspected: number
  latest_uploaded_at: string | null
  last_download_at: string | null
  touchpoints: MonitoringTp[]
}

interface Monitoring {
  generated_at: string
  accounts: MonitoringRow[]
}

const TEXT = {
  de: {
    eyebrow: 'Übungsgruppenleitung',
    title: 'KI-Briefings',
    intro: 'Sie laden die Einreichungen Ihrer Gruppen hoch und erhalten je Stammgruppe ein Briefing zur Vorbereitung des Touchpoints und ein Feedback für die Gruppe. Keine Punkte, keine Musterlösung — jede Wahl ist zulässig, beurteilt wird nur, ob die Begründung trägt.',
    helpIntro: 'So geht es: 1. ZIP-Datei hochladen. 2. Warten, bis die Verarbeitung fertig ist. 3. Erkannte Angaben prüfen. 4. Dokumente herunterladen. Alles Weitere steht im Reiter „Anleitung“.',
    // Upload
    uploadTitle: 'Einreichungen hochladen',
    uploadIntro: 'Eine ZIP-Datei mit den Einreichungen Ihrer Gruppen (PPTX aus der offiziellen Vorlage, ersatzweise DOCX oder PDF). Touchpoint, Übungsgruppe und Stammgruppe liest das System vom Deckblatt.',
    helpUpload: 'Packen Sie alle Dateien Ihrer Gruppen in eine ZIP-Datei (rechte Maustaste → „Komprimieren“ bzw. „Senden an → ZIP-komprimierter Ordner“). Die Dateien selbst und die Namen der Mitglieder werden nie gespeichert — nur die Auswertung.',
    fileLabel: 'ZIP-Datei wählen',
    upload: 'Hochladen und auswerten',
    uploading: 'Upload läuft…',
    running: (p: number, t: number) => `Verarbeitung läuft: ${p} von ${t} Dateien fertig. Sie dürfen die Seite schliessen.`,
    done: (b: BatchStatus) => `Fertig: ${b.briefed} ausgewertet · ${b.rejected ?? 0} abgelehnt · ${b.failed} nicht lesbar · ${b.review} bitte prüfen`,
    stale: 'Die Verarbeitung ist seit über 30 Minuten stehen geblieben — vermutlich durch einen Neustart abgebrochen. Bitte erneut hochladen; die neueste Auswertung je Stammgruppe zählt.',
    batches: 'Ihre letzten Uploads',
    helpBatches: 'Jede Zeile ist ein Upload: Zeitpunkt, Dateiname, Stand. „done“ heisst fertig.',
    errorGeneric: 'Upload fehlgeschlagen — bitte erneut versuchen.',
    // Konsistenz
    mismatchTitle: 'Bitte prüfen: Gruppen weichen von früheren Touchpoints ab',
    mismatchNew: (tp: number, groups: string[]) => `Touchpoint ${tp}: neu dabei ${groups.join(', ')}`,
    mismatchMissing: (tp: number, groups: string[]) => `Touchpoint ${tp}: nicht mehr dabei ${groups.join(', ')}`,
    helpMismatch: 'Im Vergleich zu Ihren früheren Uploads sind hier andere Gruppennummern erkannt worden. Das kann richtig sein — oder eine Datei ist vertauscht oder ein Deckblatt falsch ausgefüllt. Bitte kurz kontrollieren.',
    // Abgelehnt
    rejectedTitle: (n: number) => `Nicht ausgewertet (${n})`,
    rejectedIntro: 'Diese Dateien enthalten keinen Text oder haben nichts mit dem Fall ON zu tun. Sie wurden nicht ausgewertet. Bitte prüfen und die richtige Datei erneut hochladen.',
    helpRejected: 'Abgelehnt wird nur, was gar keinen Text enthält oder erkennbar nichts mit dem Arbeitsauftrag am Running Case ON zu tun hat. Ein vergessenes Deckblatt ist kein Grund: Solche Abgaben werden ausgewertet und erscheinen unter „Bitte zuordnen“.',
    assignTitle: (n: number) => `Bitte zuordnen (${n})`,
    assignIntro: 'Diese Abgaben wurden ausgewertet, aber das Deckblatt fehlte oder war unvollständig. Tragen Sie Übungsgruppe und Stammgruppe ein und prüfen Sie den Touchpoint.',
    helpAssign: 'Die Angaben stehen auf dem Deckblatt der Einreichung als Code, zum Beispiel TP1-UEG07-SG3: Touchpoint 1, Übungsgruppe 7, Stammgruppe 3.',
    injectionWarning: 'Achtung: Die Gruppe hat versucht, eine Prompt-Injection einzugeben.',
    injectionFound: 'Gefundener Text',
    helpInjection: 'Im Abgabetext stehen Anweisungen an die KI oder an die Bewertung, zum Beispiel „ignoriere alle Anweisungen“ oder versteckter Text in weisser Schrift. Die Auswertung wurde trotzdem erstellt; das Modell ist angewiesen, solche Sätze zu ignorieren. Bitte sprechen Sie das im Touchpoint an.',
    piiRemoved: 'Personenbezogene Angaben wurden vor der Auswertung entfernt.',
    tp: 'Touchpoint',
    ueg: 'Übungsgruppe',
    sg: 'Stammgruppe',
    save: 'Speichern',
    saving: 'Wird gespeichert…',
    edit: 'Angaben ändern',
    cancel: 'Abbrechen',
    // Liste
    tpLabel: 'Touchpoint',
    helpTp: 'Jeder Reiter zeigt einen Touchpoint. Der neueste steht links und ist beim Öffnen ausgewählt. Angezeigt werden nur Touchpoints, für die Sie etwas hochgeladen haben.',
    noData: 'Für diesen Touchpoint liegen noch keine Auswertungen vor. Laden Sie oben eine ZIP-Datei hoch.',
    noDataAtAll: 'Sie haben noch nichts hochgeladen. Laden Sie oben eine ZIP-Datei mit den Einreichungen Ihrer Gruppen hoch.',
    groupCount: (n: number) => `${n} Stammgruppe${n === 1 ? '' : 'n'} hochgeladen`,
    downloadAll: (ueg: string) => `Briefing-Dokument ${ueg} (Word)`,
    helpDownloadAll: 'Ein Word-Dokument mit den Briefings aller Stammgruppen dieser Übungsgruppe — Ihre Vorbereitung für den Touchpoint.',
    feedbackZip: (ueg: string) => `Feedback ${ueg} für die Stammgruppen (ZIP)`,
    helpFeedback: 'Eine ZIP-Datei mit einem Word-Dokument je Stammgruppe. Geben Sie jeder Gruppe ihr Dokument weiter, zum Beispiel über Canvas. Das Feedback nennt keine Punkte und keine Musterlösung.',
    downloadOne: 'Briefing',
    feedbackOne: 'Feedback',
    statusOk: 'Ausgewertet',
    statusRejected: 'Nicht ausgewertet',
    statusInjection: 'Prompt-Injection vermutet',
    statusReview: 'Bitte prüfen',
    statusFallback: 'Technischer Fallback — Abgabe direkt lesen',
    statusFailed: 'Datei nicht lesbar',
    statusNoContent: 'Kein Text in der Abgabe',
    helpStatus: '„Bitte prüfen“ heisst: Die Automatik war unsicher oder hat einen Textteil zurückgehalten — lesen Sie diese Abgabe direkt. „Nicht lesbar“: Datei ist beschädigt oder kein PPTX/DOCX/PDF.',
    formalChars: (b: number, n: number, max: number, ok: boolean) => `Folie ${b + 1}: ${n}/${max} Zeichen${ok ? '' : ' (über der Grenze)'}`,
    kernposition: 'Kernposition',
    argumente: 'Tragende Argumente',
    duenn: 'Dünne Stellen (Ansatz für Rückfragen)',
    einschaetzung: 'Einschätzung',
    none: '—',
    baustein: (n: number) => `Baustein ${n}`,
    questionsTitle: 'Beispiel-Rückfragen an die Gruppe',
    questionsStrengths: 'An die Stärken anknüpfen',
    questionsWeaknesses: 'Dünne Stellen aufdecken',
    helpQuestions: 'Vorschläge für Ihr Gespräch mit dieser Gruppe: zwei Fragen vertiefen, was trägt; drei Fragen decken auf, wo die Begründung dünn bleibt. Welche Fragen Sie stellen, bleibt Ihre didaktische Entscheidung.',
    feedbackTitle: 'Feedback an die Stammgruppe',
    fbTraegt: 'Was trägt',
    fbDuenn: 'Was bleibt dünn',
    fbSchritt: 'Nächster Schritt',
    fbAusblick: 'Ausblick',
    fbReview: 'Feedback bitte vor der Weitergabe prüfen',
    uploadedBy: 'hochgeladen von',
    // Master
    masterTitle: 'Monitoring (Kursleitung)',
    masterIntro: 'Je Konto: was wann hochgeladen und heruntergeladen wurde, offene Prüffälle, Passwort-Anfragen. Klappen Sie ein Konto auf, um die Gruppen je Touchpoint zu sehen und dieselben Dokumente herunterzuladen.',
    helpMaster: 'Nur der Master sieht diese Tabelle. Rot markiert sind Konten, die „Passwort vergessen“ angefragt haben — erzeugen Sie dort einen Einmalcode und schicken Sie ihn der Person per E-Mail.',
    colAccount: 'Konto',
    colUploads: 'Uploads',
    colLastUpload: 'Letzter Upload',
    colLastDownload: 'Letzter Download',
    colReview: 'Offen',
    colPassword: 'Passwort',
    pwSet: 'gesetzt',
    pwNotSet: 'noch keins',
    resetRequested: 'Zurücksetzen angefragt',
    issueCode: 'Einmalcode erzeugen',
    issuing: 'Wird erzeugt…',
    codeIssued: (code: string, until: string) => `Einmalcode: ${code} — gültig bis ${until}. Bitte per E-Mail an die Person schicken. Er wird nur jetzt angezeigt.`,
    helpCode: 'Der Code ersetzt einmalig das Passwort. Die Person meldet sich damit an und legt sofort ein neues Passwort fest. Danach ist der Code ungültig. Sie sehen kein Passwort.',
    codeActive: (until: string) => `Einmalcode aktiv bis ${until}`,
    viewAs: 'Auswertungen anzeigen von',
    helpViewAs: 'Wählen Sie ein Konto, um dessen Auswertungen unten zu sehen und herunterzuladen — genau so, wie der Übungsgruppenleiter sie sieht.',
    self: 'eigene Uploads (Master)',
    noUploads: 'noch nichts hochgeladen',
    lastBriefingDl: 'Briefing geladen',
    lastFeedbackDl: 'Feedback geladen',
    never: 'nie',
  },
  en: {
    eyebrow: 'Tutorial group lead',
    title: 'AI briefings',
    intro: 'You upload the submissions of your groups and receive, per home group, a briefing to prepare the touchpoint and feedback for the group. No points, no model solution — any choice is admissible; only the reasoning is judged.',
    helpIntro: 'How it works: 1. Upload a ZIP file. 2. Wait until processing has finished. 3. Check the detected details. 4. Download the documents. Everything else is in the “Guide” tab.',
    uploadTitle: 'Upload submissions',
    uploadIntro: 'One ZIP file with the submissions of your groups (PPTX from the official template, or DOCX/PDF). The system reads touchpoint, tutorial group and home group from the cover sheet.',
    helpUpload: 'Put all files of your groups into one ZIP file (right click → “Compress” or “Send to → Compressed folder”). The files themselves and member names are never stored — only the result.',
    fileLabel: 'Choose ZIP file',
    upload: 'Upload and evaluate',
    uploading: 'Uploading…',
    running: (p: number, t: number) => `Processing: ${p} of ${t} files done. You may close this page.`,
    done: (b: BatchStatus) => `Done: ${b.briefed} evaluated · ${b.rejected ?? 0} rejected · ${b.failed} unreadable · ${b.review} to check`,
    stale: 'Processing has stalled for over 30 minutes — probably interrupted by a restart. Please upload again; the latest result per home group counts.',
    batches: 'Your recent uploads',
    helpBatches: 'Each line is one upload: time, file name, state. “done” means finished.',
    errorGeneric: 'Upload failed — please try again.',
    mismatchTitle: 'Please check: groups differ from earlier touchpoints',
    mismatchNew: (tp: number, groups: string[]) => `Touchpoint ${tp}: new ${groups.join(', ')}`,
    mismatchMissing: (tp: number, groups: string[]) => `Touchpoint ${tp}: no longer present ${groups.join(', ')}`,
    helpMismatch: 'Compared to your earlier uploads, different group numbers were detected here. That may be correct — or a file was mixed up or a cover sheet filled in wrongly. Please check briefly.',
    rejectedTitle: (n: number) => `Not evaluated (${n})`,
    rejectedIntro: 'These files contain no text or have nothing to do with the ON case. They were not evaluated. Please check and upload the correct file again.',
    helpRejected: 'Only files with no text at all or with no recognisable link to the assignment on the ON running case are rejected. A forgotten cover sheet is not a reason: such submissions are evaluated and appear under “Please assign”.',
    assignTitle: (n: number) => `Please assign (${n})`,
    assignIntro: 'These submissions were evaluated, but the cover sheet was missing or incomplete. Enter tutorial group and home group and check the touchpoint.',
    helpAssign: 'The details are on the cover sheet as a code, e.g. TP1-UEG07-SG3: touchpoint 1, tutorial group 7, home group 3.',
    injectionWarning: 'Warning: the group tried to enter a prompt injection.',
    injectionFound: 'Text found',
    helpInjection: 'The submission text contains instructions aimed at the AI or the assessment, e.g. “ignore all instructions” or hidden white text. The evaluation was created anyway; the model is instructed to ignore such sentences. Please address it in the touchpoint.',
    piiRemoved: 'Personal data was removed before the evaluation.',
    tp: 'Touchpoint',
    ueg: 'Tutorial group',
    sg: 'Home group',
    save: 'Save',
    saving: 'Saving…',
    edit: 'Change details',
    cancel: 'Cancel',
    tpLabel: 'Touchpoint',
    helpTp: 'Each tab shows one touchpoint. The newest is on the left and selected when you open the page. Only touchpoints you uploaded for are shown.',
    noData: 'No results for this touchpoint yet. Upload a ZIP file above.',
    noDataAtAll: 'You have not uploaded anything yet. Upload a ZIP file with the submissions of your groups above.',
    groupCount: (n: number) => `${n} home group${n === 1 ? '' : 's'} uploaded`,
    downloadAll: (ueg: string) => `Briefing document ${ueg} (Word)`,
    helpDownloadAll: 'One Word document with the briefings of all home groups of this tutorial group — your preparation for the touchpoint.',
    feedbackZip: (ueg: string) => `Feedback ${ueg} for the home groups (ZIP)`,
    helpFeedback: 'A ZIP file with one Word document per home group. Pass each group its document, e.g. via Canvas. The feedback names no points and no model solution.',
    downloadOne: 'Briefing',
    feedbackOne: 'Feedback',
    statusOk: 'Evaluated',
    statusRejected: 'Not evaluated',
    statusInjection: 'Prompt injection suspected',
    statusReview: 'Please check',
    statusFallback: 'Technical fallback — read the submission directly',
    statusFailed: 'File unreadable',
    statusNoContent: 'No text in submission',
    helpStatus: '“Please check” means the automation was unsure or withheld part of the text — read that submission directly. “Unreadable”: the file is damaged or not PPTX/DOCX/PDF.',
    formalChars: (b: number, n: number, max: number, ok: boolean) => `Slide ${b + 1}: ${n}/${max} characters${ok ? '' : ' (over limit)'}`,
    kernposition: 'Core position',
    argumente: 'Supporting arguments',
    duenn: 'Thin spots (prompts for follow-up questions)',
    einschaetzung: 'Assessment',
    none: '—',
    baustein: (n: number) => `Building block ${n}`,
    questionsTitle: 'Example follow-up questions for the group',
    questionsStrengths: 'Build on the strengths',
    questionsWeaknesses: 'Uncover thin spots',
    helpQuestions: 'Suggestions for your conversation with this group: two questions deepen what holds; three uncover where the reasoning stays thin. Which questions you ask remains your didactic decision.',
    feedbackTitle: 'Feedback for the home group',
    fbTraegt: 'What holds',
    fbDuenn: 'What stays thin',
    fbSchritt: 'Next step',
    fbAusblick: 'Outlook',
    fbReview: 'Please check the feedback before passing it on',
    uploadedBy: 'uploaded by',
    masterTitle: 'Monitoring (course lead)',
    masterIntro: 'Per account: what was uploaded and downloaded when, open checks, password requests. Expand an account to see its groups per touchpoint and download the same documents.',
    helpMaster: 'Only the master sees this table. Accounts that requested “forgot password” are marked red — generate a one-time code there and e-mail it to the person.',
    colAccount: 'Account',
    colUploads: 'Uploads',
    colLastUpload: 'Last upload',
    colLastDownload: 'Last download',
    colReview: 'Open',
    colPassword: 'Password',
    pwSet: 'set',
    pwNotSet: 'none yet',
    resetRequested: 'Reset requested',
    issueCode: 'Generate one-time code',
    issuing: 'Generating…',
    codeIssued: (code: string, until: string) => `One-time code: ${code} — valid until ${until}. Please e-mail it to the person. It is shown only now.`,
    helpCode: 'The code replaces the password once. The person signs in with it and immediately sets a new password. Afterwards the code is invalid. You never see a password.',
    codeActive: (until: string) => `One-time code active until ${until}`,
    viewAs: 'Show results of',
    helpViewAs: 'Choose an account to see and download its results below — exactly as the tutorial group lead sees them.',
    self: 'own uploads (master)',
    noUploads: 'nothing uploaded yet',
    lastBriefingDl: 'briefing downloaded',
    lastFeedbackDl: 'feedback downloaded',
    never: 'never',
  },
}

const REVIEW_TONE = '#ad3f2b'
const FAIL_TONE = '#c0392b'

const fmtTime = (iso: string | null | undefined) => {
  if (!iso) return '–'
  const [d, t] = iso.split('T')
  if (!d) return iso
  const [y, m, day] = d.split('-')
  return `${day}.${m}.${y}${t ? ` ${t.slice(0, 5)}` : ''}`
}

const isRejected = (r: BriefingRecord) => r.status === 'rejected' || r.status === 'extraction_failed'
// Ausgewertet, aber Deckblatt fehlte: Übungsgruppe/Stammgruppe nachtragen
const needsAssignment = (r: BriefingRecord) => r.status === 'briefed' && (!r.ueg || !r.sg)

type Draft = { tp: string; ueg: string; sg: string }

export default function BriefingsPage() {
  const [language] = useLanguage()
  const text = TEXT[language]
  const isMaster = useClientValue(readTeacherMaster, false)

  const [viewAs, setViewAs] = useState('')          // Master: Konto, dessen Auswertungen angezeigt werden
  const [records, setRecords] = useState<BriefingRecord[]>([])
  const [batches, setBatches] = useState<BatchStatus[]>([])
  const [monitoring, setMonitoring] = useState<Monitoring | null>(null)
  const [loadError, setLoadError] = useState('')
  const [tp, setTp] = useState<number | null>(null)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [expandedAccounts, setExpandedAccounts] = useState<Record<string, boolean>>({})

  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [activeBatch, setActiveBatch] = useState<BatchStatus | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [editing, setEditing] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<Record<string, string>>({})

  const [issuing, setIssuing] = useState<string | null>(null)
  const [issuedCodes, setIssuedCodes] = useState<Record<string, { code: string; expires_at: string }>>({})

  const tutorQuery = isMaster && viewAs ? `?tutor=${encodeURIComponent(viewAs)}` : ''

  const load = useCallback(() => {
    return Promise.all([
      teacherFetch<BriefingRecord[]>(`/briefings${tutorQuery}`),
      teacherFetch<BatchStatus[]>(`/briefings/batches${tutorQuery}`),
      isMaster ? teacherFetch<Monitoring>('/briefings/monitoring') : Promise.resolve(null),
    ])
      .then(([list, batchList, mon]) => {
        setRecords(list)
        setBatches(batchList)
        setMonitoring(mon)
        setLoadError('')
      })
      .catch((e: unknown) => setLoadError(e instanceof Error ? e.message : 'API error'))
  }, [tutorQuery, isMaster])

  useEffect(() => {
    sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'teacher')
  }, [])

  useEffect(() => {
    load()
  }, [load])

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
      const res = await fetch(upload_url, { method: 'POST', body: formData, headers: { 'X-Upload-Token': token } })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(typeof err.detail === 'string' ? err.detail : text.errorGeneric)
      }
      const batch = (await res.json()) as BatchStatus
      setActiveBatch(batch)
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      if (isMaster) setViewAs('')
      load()
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : text.errorGeneric)
    } finally {
      setUploading(false)
    }
  }

  const draftFor = (r: BriefingRecord): Draft =>
    drafts[r.briefing_id] ?? { tp: r.target_tp ? String(r.target_tp) : '', ueg: r.ueg ?? '', sg: r.sg ? String(r.sg) : '' }

  const saveAssignment = async (r: BriefingRecord) => {
    const d = draftFor(r)
    if (saving) return
    const body: Record<string, unknown> = {}
    if (d.tp.trim()) body.target_tp = Number(d.tp)
    if (d.ueg.trim()) body.ueg = d.ueg.trim()
    if (d.sg.trim()) body.sg = Number(d.sg)
    if (Object.keys(body).length === 0) return
    setSaving(r.briefing_id)
    setSaveError(c => ({ ...c, [r.briefing_id]: '' }))
    try {
      await teacherFetch(`/briefings/${encodeURIComponent(r.briefing_id)}`, { method: 'PATCH', body: JSON.stringify(body) })
      setDrafts(c => { const n = { ...c }; delete n[r.briefing_id]; return n })
      setEditing(c => ({ ...c, [r.briefing_id]: false }))
      await load()
    } catch (e) {
      setSaveError(c => ({ ...c, [r.briefing_id]: e instanceof Error ? e.message : 'Error' }))
    } finally {
      setSaving(null)
    }
  }

  const issueCode = async (account: string) => {
    if (issuing) return
    setIssuing(account)
    try {
      const res = await teacherFetch<{ code: string; expires_at: string }>(`/auth/tutor/${encodeURIComponent(account)}/reset-code`, { method: 'POST' })
      setIssuedCodes(c => ({ ...c, [account]: res }))
      load()
    } catch {
      /* Tabelle bleibt */
    } finally {
      setIssuing(null)
    }
  }

  // Touchpoints als Reiter: nur die, für die etwas vorliegt; der neueste
  // steht links und ist beim Öffnen aktiv (Owner-Entscheidung 2026-09-13).
  const availableTps = useMemo(
    () => TPS.filter(n => records.some(r => r.target_tp === n)).sort((a, b) => b - a),
    [records],
  )
  const activeTp = tp && availableTps.includes(tp) ? tp : availableTps[0] ?? null

  // Konsistenz über Touchpoints: welche Gruppen sind neu/fehlen gegenüber früheren TPs?
  const mismatches = useMemo(() => {
    const byTp = new Map<number, Set<string>>()
    for (const r of records) {
      if (r.target_tp && r.ueg && r.sg) {
        byTp.set(r.target_tp, (byTp.get(r.target_tp) ?? new Set()).add(`${r.ueg}-SG${r.sg}`))
      }
    }
    const tps = [...byTp.keys()].sort((a, b) => a - b)
    const out: { tp: number; added: string[]; missing: string[] }[] = []
    const seen = new Set<string>()
    tps.forEach((t, i) => {
      const current = byTp.get(t)!
      if (i > 0) {
        const added = [...current].filter(g => !seen.has(g)).sort()
        const missing = [...seen].filter(g => !current.has(g)).sort()
        if (added.length || missing.length) out.push({ tp: t, added, missing })
      }
      current.forEach(g => seen.add(g))
    })
    return out
  }, [records])

  const rejected = records.filter(isRejected)
  const toAssign = records.filter(needsAssignment)
  const shown = records.filter(r => r.target_tp === activeTp && !isRejected(r) && !needsAssignment(r))
  const grouped = new Map<string, BriefingRecord[]>()
  for (const r of shown) grouped.set(r.ueg, [...(grouped.get(r.ueg) ?? []), r])
  const dlQuery = (extra: string) => `${extra}${isMaster && viewAs ? `&tutor=${encodeURIComponent(viewAs)}` : ''}`

  const statusOf = (r: BriefingRecord) => {
    if (r.status === 'extraction_failed') return { label: text.statusFailed, tone: FAIL_TONE }
    if (r.status === 'rejected') return { label: text.statusRejected, tone: FAIL_TONE }
    if (r.injection_suspected) return { label: text.statusInjection, tone: FAIL_TONE }
    if (r.status === 'no_content') return { label: text.statusNoContent, tone: FAIL_TONE }
    if (r.evaluation_status === 'technical_fallback') return { label: text.statusFallback, tone: FAIL_TONE }
    if (r.needs_human_review) return { label: text.statusReview, tone: REVIEW_TONE }
    return { label: text.statusOk, tone: 'var(--accent)' }
  }

  const renderAssignForm = (r: BriefingRecord) => {
    const d = draftFor(r)
    const set = (patch: Partial<Draft>) => setDrafts(c => ({ ...c, [r.briefing_id]: { ...draftFor(r), ...patch } }))
    const input = 'px-2 py-1.5 text-sm outline-none'
    const style = { border: '1px solid rgba(53,40,30,0.3)', color: 'var(--ink)', background: 'var(--field)' }
    return (
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs" style={{ color: 'var(--muted)' }}>
          {text.tp}
          <select value={d.tp} onChange={e => set({ tp: e.target.value })} className={`${input} block mt-1 w-24`} style={style}>
            <option value="">–</option>
            {TPS.map(n => <option key={n} value={n}>TP{n}</option>)}
          </select>
        </label>
        <label className="text-xs" style={{ color: 'var(--muted)' }}>
          {text.ueg}
          <input value={d.ueg} onChange={e => set({ ueg: e.target.value })} placeholder="UEG07" className={`${input} block mt-1 w-24`} style={style} />
        </label>
        <label className="text-xs" style={{ color: 'var(--muted)' }}>
          {text.sg}
          <input value={d.sg} onChange={e => set({ sg: e.target.value })} placeholder="3" inputMode="numeric" className={`${input} block mt-1 w-16`} style={style} />
        </label>
        <button type="button" onClick={() => saveAssignment(r)} disabled={saving === r.briefing_id}
          className="px-4 py-2 text-xs font-medium disabled:opacity-40" style={{ background: 'var(--ink)', color: 'var(--white)' }}>
          {saving === r.briefing_id ? text.saving : text.save}
        </button>
        {editing[r.briefing_id] && (
          <button type="button" onClick={() => setEditing(c => ({ ...c, [r.briefing_id]: false }))}
            className="px-3 py-2 text-xs" style={{ color: 'var(--muted)' }}>
            {text.cancel}
          </button>
        )}
        {saveError[r.briefing_id] && <span className="text-xs" style={{ color: FAIL_TONE }}>{saveError[r.briefing_id]}</span>}
      </div>
    )
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

  const renderQuestions = (q?: Rueckfragen) => {
    if (!q || (!q.zu_staerken?.length && !q.zu_schwaechen?.length)) return null
    return (
      <div className="mb-5 p-4" style={{ border: '1px solid var(--hairline)' }}>
        <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
          {text.questionsTitle}<HelpHint text={text.helpQuestions} />
        </p>
        <p className="text-xs font-medium mb-1">{text.questionsStrengths}</p>
        <ol className="list-decimal pl-5 text-sm mb-3">
          {(q.zu_staerken ?? []).map((item, i) => <li key={i}>{item}</li>)}
        </ol>
        <p className="text-xs font-medium mb-1">{text.questionsWeaknesses}</p>
        <ol className="list-decimal pl-5 text-sm">
          {(q.zu_schwaechen ?? []).map((item, i) => <li key={i}>{item}</li>)}
        </ol>
      </div>
    )
  }

  const renderRecord = (r: BriefingRecord, assignMode: boolean) => {
    const status = statusOf(r)
    const open = !!expanded[r.briefing_id]
    const f = r.formal ?? {}
    const isEditing = assignMode || !!editing[r.briefing_id]
    return (
      <div key={r.briefing_id}>
        <div className="flex flex-wrap items-center justify-between gap-3 py-4 px-2">
          <button type="button" className="flex items-center gap-3 flex-wrap min-w-0 text-left"
            onClick={() => setExpanded(c => ({ ...c, [r.briefing_id]: !open }))}>
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <span className="font-mono text-sm font-medium">{r.code ?? r.filename}</span>
            {r.code && <span className="font-mono text-xs" style={{ color: 'var(--muted)' }}>{r.filename}</span>}
            <span className="text-xs" style={{ color: status.tone }}>{status.label}</span>
            {isMaster && r.uploaded_by && <span className="text-xs" style={{ color: 'var(--muted)' }}>{text.uploadedBy} {r.uploaded_by}</span>}
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
              <a href={`/api/teacher/briefings/${encodeURIComponent(r.briefing_id)}/docx`}
                className="flex items-center gap-1 px-3 py-1 text-xs font-medium" style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}>
                <Download size={12} /> {text.downloadOne}
              </a>
            )}
            {r.status === 'briefed' && (r.feedback_status === 'ok' || r.feedback_status === 'technical_fallback') && (
              <a href={`/api/teacher/briefings/${encodeURIComponent(r.briefing_id)}/feedback/docx`}
                className="flex items-center gap-1 px-3 py-1 text-xs font-medium" style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}>
                <Download size={12} /> {text.feedbackOne}
              </a>
            )}
            {!assignMode && r.status === 'briefed' && !editing[r.briefing_id] && (
              <button type="button" onClick={() => setEditing(c => ({ ...c, [r.briefing_id]: true }))}
                className="flex items-center gap-1 px-3 py-1 text-xs" style={{ color: 'var(--muted)' }} title={text.edit}>
                <Pencil size={12} /> {text.edit}
              </button>
            )}
          </div>
        </div>
        {r.injection_suspected && (
          <div className="mx-2 mb-3 p-3 flex gap-2 text-sm" style={{ border: `1px solid ${FAIL_TONE}`, background: 'rgba(192,57,43,0.06)', color: FAIL_TONE }}>
            <AlertTriangle size={16} style={{ flexShrink: 0 }} />
            <div>
              <p className="font-medium">{text.injectionWarning}<HelpHint text={text.helpInjection} /></p>
              {(r.injection_findings ?? []).map((f, i) => (
                <p key={i} className="text-xs mt-1" style={{ color: 'var(--ink)' }}>{text.injectionFound}: „{f}“</p>
              ))}
            </div>
          </div>
        )}
        {r.status === 'rejected' && r.reject_reason && (
          <p className="px-8 pb-4 text-sm" style={{ color: FAIL_TONE }}>{r.reject_reason}</p>
        )}
        {isEditing && <div className="px-8 pb-4">{renderAssignForm(r)}</div>}
        {open && (
          <div className="px-8 pb-6">
            {r.review_reason && r.status !== 'rejected' && <p className="text-xs mb-4" style={{ color: REVIEW_TONE }}>{r.review_reason}</p>}
            {(r.pii_removed ?? []).length > 0 && <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{text.piiRemoved}</p>}
            {(f.notes ?? []).length > 0 && <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{f.notes!.join(' ')}</p>}
            {f.full_sentences_hint && <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{f.full_sentences_hint}</p>}
            {r.status === 'briefed' && (
              <>
                {renderBaustein(1, r.briefing?.baustein1 as BausteinBriefing | undefined)}
                {renderBaustein(2, r.briefing?.baustein2 as BausteinBriefing | undefined)}
                {renderQuestions(r.briefing?.rueckfragen as Rueckfragen | undefined)}
              </>
            )}
            {r.status === 'briefed' && r.feedback && r.feedback.baustein1 && (
              <div className="mt-6 p-4" style={{ background: 'var(--surface)', border: '1px solid var(--hairline)' }}>
                <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.feedbackTitle}</p>
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

  const renderMonitoring = (mon: Monitoring) => (
    <div className="mb-14">
      <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>{text.masterTitle}</p>
      <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
        {text.masterIntro}
        <HelpHint text={text.helpMaster} />
      </p>
      <div className="flex flex-wrap items-center gap-3 mb-4 text-sm">
        <span style={{ color: 'var(--muted)' }}>{text.viewAs}<HelpHint text={text.helpViewAs} /></span>
        <select value={viewAs} onChange={e => setViewAs(e.target.value)} className="px-3 py-1.5 text-sm outline-none"
          style={{ border: '1px solid rgba(53,40,30,0.3)', color: 'var(--ink)', background: 'var(--field)' }}>
          <option value="">{text.self}</option>
          {mon.accounts.filter(a => !a.is_master).map(a => (
            <option key={a.account} value={a.account}>{a.account}{a.upload_count ? ` (${a.upload_count})` : ''}</option>
          ))}
        </select>
      </div>
      <div className="overflow-x-auto" style={{ border: '1px solid var(--hairline)' }}>
        <table className="w-full text-xs" style={{ minWidth: 720 }}>
          <thead>
            <tr style={{ background: 'var(--surface)' }}>
              {[text.colAccount, text.colUploads, text.colLastUpload, text.colLastDownload, text.colReview, text.colPassword].map(h => (
                <th key={h} className="text-left px-3 py-2 font-medium" style={{ color: 'var(--muted)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mon.accounts.map(a => {
              const open = !!expandedAccounts[a.account]
              const issued = issuedCodes[a.account]
              const flagged = !!a.reset_requested_at
              return [
                <tr key={a.account} style={{ borderTop: '1px solid var(--hairline)', background: flagged ? 'rgba(192,57,43,0.06)' : undefined }}>
                  <td className="px-3 py-2">
                    <button type="button" className="flex items-center gap-2 font-mono font-medium" onClick={() => setExpandedAccounts(c => ({ ...c, [a.account]: !open }))}>
                      {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      {a.account}
                    </button>
                  </td>
                  <td className="px-3 py-2">{a.upload_count || <span style={{ color: 'var(--muted)' }}>{text.noUploads}</span>}</td>
                  <td className="px-3 py-2 font-mono">{fmtTime(a.latest_uploaded_at)}</td>
                  <td className="px-3 py-2 font-mono">{a.last_download_at ? fmtTime(a.last_download_at) : text.never}</td>
                  <td className="px-3 py-2" style={{ color: a.review_open ? REVIEW_TONE : undefined }}>{a.review_open}</td>
                  <td className="px-3 py-2">
                    {a.is_tutor_account ? (
                      <span className="flex flex-wrap items-center gap-2">
                        <span style={{ color: a.password_set ? 'var(--accent)' : 'var(--muted)' }}>{a.password_set ? text.pwSet : text.pwNotSet}</span>
                        {flagged && (
                          <span className="flex items-center gap-1 font-medium" style={{ color: FAIL_TONE }}>
                            <KeyRound size={12} /> {text.resetRequested} ({fmtTime(a.reset_requested_at)})
                          </span>
                        )}
                        {a.reset_code_active && !issued && <span style={{ color: 'var(--muted)' }}>{text.codeActive(fmtTime(a.reset_code_expires_at))}</span>}
                        {(flagged || a.password_set) && (
                          <button type="button" onClick={() => issueCode(a.account)} disabled={issuing === a.account}
                            className="px-2 py-1 font-medium disabled:opacity-40" style={{ border: '1px solid rgba(53,40,30,0.3)', color: 'var(--ink)' }}>
                            {issuing === a.account ? text.issuing : text.issueCode}
                          </button>
                        )}
                        <HelpHint text={text.helpCode} />
                      </span>
                    ) : <span style={{ color: 'var(--muted)' }}>–</span>}
                    {issued && (
                      <p className="mt-2 p-2 font-mono" style={{ background: 'rgba(21,99,61,0.08)', color: 'var(--ink)' }}>
                        {text.codeIssued(issued.code, fmtTime(issued.expires_at))}
                      </p>
                    )}
                  </td>
                </tr>,
                open && (
                  <tr key={`${a.account}-detail`} style={{ background: 'var(--surface)' }}>
                    <td colSpan={6} className="px-6 py-4">
                      {a.touchpoints.length === 0 && <p style={{ color: 'var(--muted)' }}>{text.noUploads}</p>}
                      {a.touchpoints.map(t => (
                        <div key={t.target_tp} className="mb-4">
                          <div className="flex flex-wrap items-center gap-3 mb-2">
                            <span className="font-medium">TP{t.target_tp || '?'}</span>
                            <span style={{ color: 'var(--muted)' }}>{t.briefed}/{t.count} · {text.lastBriefingDl}: {t.last_download_briefing_at ? fmtTime(t.last_download_briefing_at) : text.never} · {text.lastFeedbackDl}: {t.last_download_feedback_at ? fmtTime(t.last_download_feedback_at) : text.never}</span>
                            {t.target_tp > 0 && t.briefed > 0 && (
                              <>
                                <a href={`/api/teacher/briefings/docx?tp=${t.target_tp}&tutor=${encodeURIComponent(a.account)}`}
                                  className="flex items-center gap-1 px-2 py-1 font-medium" style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}>
                                  <Download size={11} /> {text.downloadOne}
                                </a>
                                <a href={`/api/teacher/briefings/feedback/zip?tp=${t.target_tp}&tutor=${encodeURIComponent(a.account)}`}
                                  className="flex items-center gap-1 px-2 py-1 font-medium" style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}>
                                  <Download size={11} /> {text.feedbackOne}
                                </a>
                              </>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {t.groups.map(g => (
                              <span key={g.briefing_id} className="font-mono px-2 py-0.5" title={`${g.filename ?? ''} · ${fmtTime(g.uploaded_at)}${g.reject_reason ? ` · ${g.reject_reason}` : ''}${g.injection_suspected ? ` · ${text.injectionWarning}` : ''}`}
                                style={{ border: `1px solid ${g.injection_suspected ? FAIL_TONE : 'var(--hairline)'}`, color: g.injection_suspected || g.status !== 'briefed' ? FAIL_TONE : g.needs_human_review ? REVIEW_TONE : 'var(--ink)' }}>
                                {g.injection_suspected ? '! ' : ''}{g.code ?? g.filename}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </td>
                  </tr>
                ),
              ]
            })}
          </tbody>
        </table>
      </div>
    </div>
  )

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

        {isMaster && monitoring && renderMonitoring(monitoring)}

        {/* Upload — für alle */}
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
            <input ref={fileInputRef} type="file" accept=".zip,application/zip" onChange={e => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <button type="button" onClick={submitUpload} disabled={!file || uploading}
              className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium disabled:opacity-40" style={{ background: 'var(--ink)', color: 'var(--white)' }}>
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
            {activeBatch && activeBatch.status === 'done' && <span className="text-sm" style={{ color: 'var(--accent)' }}>{text.done(activeBatch)}</span>}
            {activeBatch && (activeBatch.stale || activeBatch.status === 'failed') && (
              <span className="text-sm" style={{ color: FAIL_TONE }}>{activeBatch.error ?? text.stale}</span>
            )}
          </div>
          {batches.length > 0 && (
            <div>
              <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>{text.batches}<HelpHint text={text.helpBatches} /></p>
              <ul className="text-xs flex flex-col gap-1" style={{ color: 'var(--muted)' }}>
                {batches.slice(0, 5).map(b => (
                  <li key={b.batch_id} className="font-mono">
                    {fmtTime(b.started_at)} · {b.filename || b.batch_id.slice(0, 8)} · {b.tps.length ? b.tps.map(n => `TP${n}`).join('+') : '–'} · {b.status}
                    {b.stale ? ' (stale)' : ''} · {b.processed}/{b.total} · {text.done(b)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {loadError && <p className="text-sm mb-6" style={{ color: FAIL_TONE }}>{loadError}</p>}

        {/* Rotes Ausrufezeichen: Gruppen weichen zwischen Touchpoints ab */}
        {mismatches.length > 0 && (
          <div className="p-4 mb-10 flex gap-3" style={{ border: `1px solid ${FAIL_TONE}`, background: 'rgba(192,57,43,0.05)' }}>
            <AlertTriangle size={20} style={{ color: FAIL_TONE, flexShrink: 0 }} />
            <div className="text-sm">
              <p className="font-medium mb-1" style={{ color: FAIL_TONE }}>{text.mismatchTitle}<HelpHint text={text.helpMismatch} /></p>
              <ul className="flex flex-col gap-0.5" style={{ color: 'var(--ink)' }}>
                {mismatches.map(m => (
                  <li key={m.tp}>
                    {m.added.length > 0 && <span>{text.mismatchNew(m.tp, m.added)}</span>}
                    {m.added.length > 0 && m.missing.length > 0 && ' · '}
                    {m.missing.length > 0 && <span>{text.mismatchMissing(m.tp, m.missing)}</span>}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Nicht ausgewertet (abgelehnt oder unlesbar) */}
        {rejected.length > 0 && (
          <div className="mb-12">
            <p className="text-xs tracking-widest uppercase mb-2" style={{ color: FAIL_TONE }}>{text.rejectedTitle(rejected.length)}</p>
            <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{text.rejectedIntro}<HelpHint text={text.helpRejected} /></p>
            <div className="divider" />
            {rejected.map(r => renderRecord(r, false))}
          </div>
        )}

        {/* Ausgewertet ohne vollständiges Deckblatt: nachtragen */}
        {toAssign.length > 0 && (
          <div className="mb-12">
            <p className="text-xs tracking-widest uppercase mb-2" style={{ color: REVIEW_TONE }}>{text.assignTitle(toAssign.length)}</p>
            <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{text.assignIntro}<HelpHint text={text.helpAssign} /></p>
            <div className="divider" />
            {toAssign.map(r => renderRecord(r, true))}
          </div>
        )}

        {records.length === 0 && !loadError && (
          <p className="py-10 text-sm text-center" style={{ color: 'var(--muted)' }}>{text.noDataAtAll}</p>
        )}

        {availableTps.length > 0 && (
          <div className="flex flex-wrap items-end gap-8 mb-10">
            <div>
              <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.tpLabel}<HelpHint text={text.helpTp} /></p>
              <div className="flex items-center gap-1 p-1 w-fit" style={{ border: '1px solid var(--hairline)' }}>
                {availableTps.map(n => (
                  <button key={n} type="button" onClick={() => setTp(n)} className="px-4 py-1.5 text-xs font-medium transition-colors"
                    style={{ background: activeTp === n ? 'var(--ink)' : 'transparent', color: activeTp === n ? 'var(--white)' : 'var(--ink)' }}
                    aria-pressed={activeTp === n}>
                    TP{n}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTp && shown.length === 0 && rejected.length === 0 && toAssign.length === 0 && (
          <p className="py-10 text-sm text-center" style={{ color: 'var(--muted)' }}>{text.noData}</p>
        )}

        {/* Auswertungen je Übungsgruppe */}
        {[...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([ueg, items]) => {
          const briefed = items.filter(r => r.status === 'briefed')
          const withFeedback = briefed.filter(r => r.feedback_status === 'ok' || r.feedback_status === 'technical_fallback')
          return (
            <div key={ueg} className="mb-12">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div>
                  <p className="text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>{ueg}</p>
                  <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>{text.groupCount(items.length)}<HelpHint text={text.helpStatus} /></p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {briefed.length > 0 && (
                    <span className="flex items-center">
                      <a href={`/api/teacher/briefings/docx${dlQuery(`?tp=${activeTp}&ueg=${encodeURIComponent(ueg)}`)}`}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium" style={{ background: 'var(--ink)', color: 'var(--white)' }}>
                        <Download size={14} /> {text.downloadAll(ueg)}
                      </a>
                      <HelpHint text={text.helpDownloadAll} />
                    </span>
                  )}
                  {withFeedback.length > 0 && (
                    <span className="flex items-center">
                      <a href={`/api/teacher/briefings/feedback/zip${dlQuery(`?tp=${activeTp}&ueg=${encodeURIComponent(ueg)}`)}`}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium" style={{ border: '1px solid var(--ink)', color: 'var(--ink)' }}>
                        <Download size={14} /> {text.feedbackZip(ueg)}
                      </a>
                      <HelpHint text={text.helpFeedback} />
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
