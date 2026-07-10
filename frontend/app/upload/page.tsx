'use client'

import { useEffect, useRef, useState } from 'react'
import Nav from '@/components/Nav'
import HelpHint from '@/components/HelpHint'
import { teacherFetch } from '@/lib/api'
import { APP_MODE_STORAGE_KEY } from '@/lib/appMode'
import { useLanguage } from '@/lib/useLanguage'
import { FileUp, Loader2 } from 'lucide-react'

// Master-Tutor-Upload: ZIP mit außerhalb der Plattform erstellten
// Gruppenarbeiten (PDFs mit einheitlichem Deckblatt inkl. Gruppenindikator).
// Jedes Dokument wird gegen die TP-Rubric des gewählten Touchpoints bewertet;
// die Ergebnisse fließen als zweite Datenquelle ins Gruppen-Dashboard.
// Zugriff: Middleware + Teacher-Proxy erzwingen das Master-Flag der Session.

interface GroupUploadRecord {
  upload_id: string
  batch_id: string
  filename: string
  group_code: string
  target_tp: number
  status: string
  uploaded_at: string
  evaluated_at: string | null
  total_points: number
  max_points: number
  percentage: number
  needs_human_review: boolean
  evaluation_status: string
}

interface BatchResponse {
  batch_id: string
  target_tp: number
  uploads: GroupUploadRecord[]
  evaluated_count: number
  unassigned_count: number
  failed_count: number
}

const UPLOAD_TEXT = {
  de: {
    eyebrow: 'Master-Tutor',
    title: 'Upload',
    intro: 'ZIP-Datei mit den Gruppenarbeiten (PDFs) hochladen. Jedes Dokument wird dem Gruppenindikator auf dem Deckblatt zugeordnet und nach denselben TP-Rubrics bewertet wie die Individualabgaben. Die Ergebnisse erscheinen im Gruppen-Dashboard.',
    tpLabel: 'Touchpoint der Abgabe',
    fileLabel: 'ZIP-Datei wählen',
    fileHint: 'Nur .zip mit PDFs. Deckblatt mit Gruppenindikator (z.B. „Gruppe 12").',
    upload: 'Hochladen & bewerten',
    uploading: 'Bewertung läuft — bitte Seite nicht schließen…',
    batchDone: (e: number, u: number, f: number) =>
      `${e} Dokument(e) bewertet · ${u} ohne Gruppenzuordnung · ${f} nicht lesbar`,
    resultsTitle: (n: number) => `Bewertete Gruppenarbeiten (${n})`,
    reviewTitle: (n: number) => `Zuordnung offen (${n})`,
    reviewHint: 'Bei diesen Dokumenten wurde kein Gruppenindikator auf dem Deckblatt erkannt. Gruppencode eintragen, dann zählt die Bewertung zur Gruppe.',
    colFile: 'Datei',
    colGroup: 'Gruppe',
    colTp: 'TP',
    colScore: 'Score',
    colStatus: 'Status',
    statusOk: 'bewertet',
    statusReview: 'Review',
    statusFallback: 'Technischer Fallback — manuell bewerten',
    statusFailed: 'PDF nicht lesbar (Scan ohne OCR?)',
    assign: 'Zuordnen',
    groupPlaceholder: 'z.B. G12',
    noData: 'Noch keine Gruppenarbeiten hochgeladen.',
    errorGeneric: 'Upload fehlgeschlagen — bitte erneut versuchen.',
    helpUpload: 'Die ZIP-Datei wird nicht gespeichert — nur der extrahierte Text wird bewertet und verworfen. Gespeichert werden ausschließlich die Bewertungsergebnisse (Scores, Gruppencode, Dateiname).',
  },
  en: {
    eyebrow: 'Master tutor',
    title: 'Upload',
    intro: 'Upload a ZIP with the group assignments (PDFs). Each document is matched to the group indicator on its cover page and evaluated against the same TP rubrics as the individual submissions. Results appear in the group dashboard.',
    tpLabel: 'Touchpoint of this submission round',
    fileLabel: 'Choose ZIP file',
    fileHint: 'Only .zip containing PDFs. Cover page with group indicator (e.g. "Group 12").',
    upload: 'Upload & evaluate',
    uploading: 'Evaluation running — please keep this page open…',
    batchDone: (e: number, u: number, f: number) =>
      `${e} document(s) evaluated · ${u} without group match · ${f} unreadable`,
    resultsTitle: (n: number) => `Evaluated group assignments (${n})`,
    reviewTitle: (n: number) => `Assignment pending (${n})`,
    reviewHint: 'No group indicator was detected on the cover page of these documents. Enter the group code to attach the evaluation to a group.',
    colFile: 'File',
    colGroup: 'Group',
    colTp: 'TP',
    colScore: 'Score',
    colStatus: 'Status',
    statusOk: 'evaluated',
    statusReview: 'Review',
    statusFallback: 'Technical fallback — grade manually',
    statusFailed: 'PDF unreadable (scan without OCR?)',
    assign: 'Assign',
    groupPlaceholder: 'e.g. G12',
    noData: 'No group assignments uploaded yet.',
    errorGeneric: 'Upload failed — please try again.',
    helpUpload: 'The ZIP file itself is never stored — only the extracted text is evaluated and discarded. Only the evaluation results (scores, group code, filename) are persisted.',
  },
}

export default function UploadPage() {
  const [language] = useLanguage()
  const text = UPLOAD_TEXT[language]

  const [targetTp, setTargetTp] = useState(1)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [batchInfo, setBatchInfo] = useState<string>('')
  const [error, setError] = useState('')
  const [records, setRecords] = useState<GroupUploadRecord[]>([])
  const [assignDrafts, setAssignDrafts] = useState<Record<string, string>>({})
  const [assigning, setAssigning] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadRecords = () => {
    teacherFetch<GroupUploadRecord[]>('/group-uploads').then(setRecords).catch(() => setRecords([]))
  }

  useEffect(() => {
    sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'teacher')
    loadRecords()
  }, [])

  const submit = async () => {
    if (!file || uploading) return
    setUploading(true)
    setError('')
    setBatchInfo('')
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('target_tp', String(targetTp))
      const res = await fetch('/api/teacher/group-uploads', {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(typeof err.detail === 'string' ? err.detail : text.errorGeneric)
      }
      const batch: BatchResponse = await res.json()
      setBatchInfo(text.batchDone(batch.evaluated_count, batch.unassigned_count, batch.failed_count))
      setFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      loadRecords()
    } catch (e) {
      setError(e instanceof Error ? e.message : text.errorGeneric)
    } finally {
      setUploading(false)
    }
  }

  const assignGroup = async (uploadId: string) => {
    const draft = (assignDrafts[uploadId] ?? '').trim()
    if (!draft || assigning) return
    setAssigning(uploadId)
    try {
      await teacherFetch(`/group-uploads/${encodeURIComponent(uploadId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group_code: draft }),
      })
      setAssignDrafts(current => ({ ...current, [uploadId]: '' }))
      loadRecords()
    } catch {
      /* Zuordnung bleibt offen — erneut versuchen */
    } finally {
      setAssigning(null)
    }
  }

  const statusLabel = (record: GroupUploadRecord) => {
    if (record.status === 'extraction_failed') return { label: text.statusFailed, tone: '#c0392b' }
    if (record.evaluation_status === 'technical_fallback') return { label: text.statusFallback, tone: '#c0392b' }
    if (record.needs_human_review) return { label: text.statusReview, tone: '#ad3f2b' }
    return { label: text.statusOk, tone: 'var(--accent)' }
  }

  const unassigned = records.filter(r => r.status === 'evaluated' && !r.group_code)
  const assigned = records.filter(r => !(r.status === 'evaluated' && !r.group_code))

  const renderRow = (record: GroupUploadRecord, editable: boolean) => {
    const status = statusLabel(record)
    return (
      <div key={record.upload_id}>
        <div className="flex flex-wrap items-center justify-between gap-3 py-4 px-2">
          <div className="flex items-center gap-4 flex-wrap min-w-0">
            <span className="font-mono text-sm font-medium break-all">{record.filename}</span>
            <span className="text-xs px-2 py-0.5" style={{ background: 'rgba(53,40,30,0.08)' }}>
              TP{record.target_tp}
            </span>
            {record.group_code && (
              <span className="font-mono text-xs px-2 py-0.5" style={{ background: 'rgba(53,40,30,0.08)' }}>
                {record.group_code}
              </span>
            )}
            <span className="text-xs" style={{ color: status.tone }}>{status.label}</span>
          </div>
          <div className="flex items-center gap-4 shrink-0">
            {record.status === 'evaluated' && (
              <span className="text-sm font-medium tabular-nums">
                {record.total_points.toFixed(1)}/{record.max_points.toFixed(0)} · {record.percentage.toFixed(0)}%
              </span>
            )}
            {editable && (
              <span className="flex items-center gap-2">
                <input
                  value={assignDrafts[record.upload_id] ?? ''}
                  onChange={e => setAssignDrafts(current => ({ ...current, [record.upload_id]: e.target.value }))}
                  placeholder={text.groupPlaceholder}
                  className="px-2 py-1 text-xs bg-transparent outline-none w-24"
                  style={{ border: '1px solid var(--hairline)', color: 'var(--ink)' }}
                />
                <button
                  type="button"
                  onClick={() => assignGroup(record.upload_id)}
                  disabled={assigning === record.upload_id || !(assignDrafts[record.upload_id] ?? '').trim()}
                  className="px-3 py-1 text-xs font-medium disabled:opacity-40"
                  style={{ background: 'var(--ink)', color: 'var(--white)' }}
                >
                  {text.assign}
                </button>
              </span>
            )}
          </div>
        </div>
        <div className="divider" />
      </div>
    )
  }

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-5xl mx-auto">
        <div className="mb-10">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
            {text.eyebrow}
          </p>
          <h1 className="font-display text-5xl leading-none flex items-center gap-4">
            <FileUp size={40} />
            {text.title}
          </h1>
        </div>

        <p className="text-sm max-w-3xl mb-10" style={{ color: 'var(--muted)' }}>
          {text.intro}
          <HelpHint text={text.helpUpload} />
        </p>

        {/* Upload-Formular */}
        <div className="p-6 mb-12 flex flex-col gap-6" style={{ background: 'var(--surface)', border: '1px solid var(--hairline)' }}>
          <div>
            <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.tpLabel}</p>
            <div className="flex items-center gap-1 p-1 w-fit" style={{ border: '1px solid var(--hairline)' }}>
              {[1, 2, 3, 4].map(tp => (
                <button
                  key={tp}
                  type="button"
                  onClick={() => setTargetTp(tp)}
                  className="px-4 py-1.5 text-xs font-medium transition-colors"
                  style={{
                    background: targetTp === tp ? 'var(--ink)' : 'transparent',
                    color: targetTp === tp ? 'var(--white)' : 'var(--ink)',
                  }}
                  aria-pressed={targetTp === tp}
                >
                  TP{tp}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>{text.fileLabel}</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip,application/zip"
              onChange={e => setFile(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
            <p className="text-xs mt-2" style={{ color: 'var(--muted)' }}>{text.fileHint}</p>
          </div>

          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={submit}
              disabled={!file || uploading}
              className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium disabled:opacity-40"
              style={{ background: 'var(--ink)', color: 'var(--white)' }}
            >
              {uploading && <Loader2 size={14} className="animate-spin" />}
              {uploading ? text.uploading : text.upload}
            </button>
            {batchInfo && <span className="text-sm" style={{ color: 'var(--accent)' }}>{batchInfo}</span>}
            {error && <span className="text-sm" style={{ color: '#c0392b' }}>{error}</span>}
          </div>
        </div>

        {/* Zuordnung offen */}
        {unassigned.length > 0 && (
          <div className="mb-12">
            <p className="text-xs tracking-widest uppercase mb-2" style={{ color: 'var(--muted)' }}>
              {text.reviewTitle(unassigned.length)}
            </p>
            <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>{text.reviewHint}</p>
            <div className="divider" />
            {unassigned.map(record => renderRow(record, true))}
          </div>
        )}

        {/* Ergebnisliste */}
        <div>
          <p className="text-xs tracking-widest uppercase mb-4" style={{ color: 'var(--muted)' }}>
            {text.resultsTitle(assigned.length)}
          </p>
          <div className="divider" />
          {assigned.length === 0 ? (
            <p className="py-10 text-sm text-center" style={{ color: 'var(--muted)' }}>{text.noData}</p>
          ) : (
            assigned.map(record => renderRow(record, false))
          )}
        </div>
      </main>
    </>
  )
}
