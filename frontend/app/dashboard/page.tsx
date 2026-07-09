'use client'

import { useEffect, useState } from 'react'
import Nav from '@/components/Nav'
import HelpHint from '@/components/HelpHint'
import NotionIcon from '@/components/NotionIcon'
import TeacherIntro from '@/components/TeacherIntro'
import { teacherFetch } from '@/lib/api'
import { APP_MODE_STORAGE_KEY } from '@/lib/appMode'
import { Locale } from '@/lib/i18n'
import { useLanguage } from '@/lib/useLanguage'
import { Users, TrendingUp } from 'lucide-react'

// Tutor-Sicht: ausschließlich Aggregate. Einzelprofile liegen hinter dem
// Forschungs-Key (X-Research-Key) und sind über den Teacher-Proxy nicht
// erreichbar — bewusst, siehe Datenschutz-Zusage im Studierenden-Login.

interface LearningObjectiveScore { tag: string; avg_pct: number; n: number }
interface Overview {
  total_students: number; total_submissions: number; avg_percentage: number
  avg_canvas_alignment_pct: number; avg_rubric_fit_pct: number
  exemplar_submissions_count: number
  needs_human_review_count: number
  technical_fallback_count: number
  by_tp: Record<number, number>; by_bloom: Record<number, number>
  top_objectives: LearningObjectiveScore[]
}
interface PenaltyCount { text: string; count: number }
interface GroupObjective { tag: string; avg_pct: number; members_below: number; members_total: number }
interface GroupSummary {
  group_code: string
  members_active: number
  submissions_count: number
  avg_percentage: number
  needs_human_review_count: number
  technical_fallback_count: number
  paste_heavy_answers: number
  attention_high: number
  attention_medium: number
  attention_low: number
}
interface GroupDetail extends GroupSummary {
  weak_objectives: GroupObjective[]
  weak_blooms: Record<number, number>
  common_penalties: PenaltyCount[]
  missing_canvas_blocks: PenaltyCount[]
}

const BLOOM: Record<Locale, Record<number, string>> = {
  de: { 2: 'Verstehen', 3: 'Anwenden', 4: 'Analysieren', 5: 'Evaluieren', 6: 'Synthese' },
  en: { 2: 'Understand', 3: 'Apply', 4: 'Analyze', 5: 'Evaluate', 6: 'Synthesize' },
}
const OBJECTIVE_LABELS: Record<string, string> = {
  analyse: 'Analyse',
  evaluieren: 'Evaluieren',
  integration: 'Integration',
  kpi: 'KPI',
  reflexion: 'Reflexion',
  transfer: 'Transfer',
  'trade-off': 'Trade-off',
}

const DASHBOARD_TEXT = {
  de: {
    eyebrow: 'Tutor-Dashboard',
    title: 'Dashboard',
    students: 'Aktive Studierende',
    submissions: 'Submissions',
    averageScore: 'Ø Score',
    averageCanvas: 'Ø Business Model Canvas',
    exemplars: 'Exemplars',
    reviewFallback: 'Review/Fallback',
    byBloom: 'Nach Bloom-Stufe',
    byTp: 'Nach TP',
    weakestObjectives: 'Schwächste Lernziele (Kohorte)',
    groups: (count: number) => `Gruppen (${count})`,
    searchPlaceholder: 'Gruppe suchen...',
    groupHint: 'Zusammenfassungen pro Übungsgruppe. Einzelprofile werden aus Datenschutzgründen nicht angezeigt.',
    members: (n: number) => `${n} aktiv`,
    needsAttention: 'mit Unterstützungsbedarf',
    watch: 'beobachten',
    onTrack: 'unauffällig',
    review: 'Review',
    pasteHint: (n: number) => `${n} Antwort(en) mit hohem Paste-Anteil (Hinweis, kein Beweis)`,
    weakObjectives: 'Schwache Lernziele',
    membersBelow: (b: number, total: number) => `${b} von ${total} Mitgliedern unter Schwelle`,
    weakBlooms: 'Schwache Bloom-Stufen (Mitglieder unter Schwelle)',
    commonPenalties: 'Häufigste Schwächen in der Gruppe',
    missingBlocks: 'Häufig fehlende Canvas-Blöcke',
    noData: 'Noch keine Daten.',
    noFindings: 'Keine auffälligen Schwierigkeiten.',
    ungrouped: 'Ohne Gruppenangabe',
    introTitle: 'Kurzanleitung: Dein Dashboard in 60 Sekunden',
    introSteps: [
      'Oben siehst du Kennzahlen über alle Studierenden hinweg — sie geben das Gesamtbild, nicht den Einzelfall.',
      'Der Kern ist die Gruppen-Liste unten: Klicke eine Gruppe auf, um zu sehen, wo sie hakt — als Vorbereitung auf deine Präsenzphase.',
      '„Mit Unterstützungsbedarf" heißt: mehrere schwache Lernziele oder sehr niedrige Scores. Sprich Themen an, keine Personen — Einzelprofile siehst du bewusst nicht.',
      'Der Copy-Paste-Anteil ist ein HINWEIS auf mögliche KI-Nutzung, kein Beweis — bitte nie als Vorwurf verwenden.',
      'Alle Zahlen stammen aus der individuellen Vorbereitung im Tool, nicht aus der Gruppenabgabe.',
    ],
    introHint: 'Die ?-Symbole neben den Abschnitten erklären jede Ansicht — sie bleiben dauerhaft verfügbar.',
    introDismiss: 'Verstanden',
    helpKpis: 'Kennzahlen über alle aktiven Studierenden. „Review/Fallback": Antworten, bei denen die automatische Bewertung unsicher war (Review) oder technisch scheiterte (Fallback) — diese Antworten verdienen deinen menschlichen Blick zuerst.',
    helpBloom: 'Durchschnittliche Leistung nach Denk-Niveau (Bloom-Taxonomie): Verstehen ist einfacher als Analysieren oder Synthese. Niedrige Werte auf hohen Stufen sind normal — auffällig sind Einbrüche auf niedrigen Stufen.',
    helpObjectives: 'Lernziele, bei denen die Kohorte im Schnitt am schwächsten abschneidet — gute Kandidaten für den Fokus deiner nächsten Präsenzphase.',
    helpGroups: 'Eine Zeile pro Übungsgruppe (Selbstauskunft der Studierenden beim Login — Tippfehler erscheinen als eigene Gruppe). Aufklappen zeigt schwache Lernziele („x von y Mitgliedern unter 60 %"), häufige Schwächen in Worten und Bloom-Stufen. Einzelpersonen werden aus Datenschutzgründen nie angezeigt.',
  },
  en: {
    eyebrow: 'Tutor dashboard',
    title: 'Dashboard',
    students: 'Active students',
    submissions: 'Submissions',
    averageScore: 'Avg. score',
    averageCanvas: 'Avg. Business Model Canvas',
    exemplars: 'Exemplars',
    reviewFallback: 'Review/Fallback',
    byBloom: 'By Bloom level',
    byTp: 'By TP',
    weakestObjectives: 'Weakest learning objectives (cohort)',
    groups: (count: number) => `Groups (${count})`,
    searchPlaceholder: 'Search group...',
    groupHint: 'Summaries per tutorial group. Individual profiles are not shown for privacy reasons.',
    members: (n: number) => `${n} active`,
    needsAttention: 'need support',
    watch: 'watch',
    onTrack: 'on track',
    review: 'Review',
    pasteHint: (n: number) => `${n} answer(s) with high paste share (indicator, not proof)`,
    weakObjectives: 'Weak objectives',
    membersBelow: (b: number, total: number) => `${b} of ${total} members below threshold`,
    weakBlooms: 'Weak Bloom levels (members below threshold)',
    commonPenalties: 'Most common weaknesses in this group',
    missingBlocks: 'Frequently missing canvas blocks',
    noData: 'No data yet.',
    noFindings: 'No notable difficulties.',
    ungrouped: 'No group specified',
    introTitle: 'Quick guide: your dashboard in 60 seconds',
    introSteps: [
      'The numbers at the top aggregate across all students — they give the big picture, not individual cases.',
      'The core is the group list below: expand a group to see where it struggles — as preparation for your in-person session.',
      '"Need support" means several weak objectives or very low scores. Address topics, not people — you deliberately never see individual profiles.',
      'The copy-paste share is an INDICATOR of possible AI use, not proof — never use it as an accusation.',
      'All numbers come from individual preparation in the tool, not from the group submission.',
    ],
    introHint: 'The ?-icons next to each section explain every view — they stay available permanently.',
    introDismiss: 'Got it',
    helpKpis: 'Metrics across all active students. "Review/Fallback": answers where automatic scoring was uncertain (review) or failed technically (fallback) — these deserve your human eye first.',
    helpBloom: 'Average performance by thinking level (Bloom taxonomy): understanding is easier than analysis or synthesis. Low values on high levels are normal — drops on low levels are the anomaly.',
    helpObjectives: 'Learning objectives where the cohort is weakest on average — good candidates for the focus of your next in-person session.',
    helpGroups: 'One row per tutorial group (self-reported at login — typos appear as separate groups). Expanding shows weak objectives ("x of y members below 60%"), common weaknesses in words, and Bloom levels. Individuals are never shown for privacy reasons.',
  },
}

function objectiveLabel(tag: string) {
  return OBJECTIVE_LABELS[tag] ?? tag
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map(part => part.length <= 3 ? part.toUpperCase() : part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function MiniBar({ pct, label }: { pct: number; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs w-24 shrink-0" style={{ color: 'var(--muted)' }}>{label}</span>
      <div className="flex-1 h-1.5" style={{ background: 'rgba(53,40,30,0.1)' }}>
        <div className="h-full transition-all duration-700" style={{ width: `${pct}%`, background: 'var(--accent)' }} />
      </div>
      <span className="text-xs w-10 text-right font-medium">{pct.toFixed(0)}%</span>
    </div>
  )
}

const UNGROUPED = 'OHNE-GRUPPE'

export default function DashboardPage() {
  const [language] = useLanguage()
  const [overview, setOverview] = useState<Overview | null>(null)
  const [groups, setGroups] = useState<GroupSummary[]>([])
  const [details, setDetails] = useState<Record<string, GroupDetail>>({})
  const [expanded, setExpanded] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const text = DASHBOARD_TEXT[language]

  useEffect(() => {
    sessionStorage.setItem(APP_MODE_STORAGE_KEY, 'teacher')
    teacherFetch<Overview>('/dashboard/overview').then(setOverview).catch(() => setOverview(null))
    teacherFetch<GroupSummary[]>('/dashboard/groups').then(setGroups).catch(() => setGroups([]))
  }, [])

  const toggleGroup = async (code: string) => {
    if (expanded === code) { setExpanded(null); return }
    setExpanded(code)
    if (!details[code]) {
      try {
        const detail = await teacherFetch<GroupDetail>(`/dashboard/groups/${encodeURIComponent(code)}`)
        setDetails(current => ({ ...current, [code]: detail }))
      } catch { /* Detail bleibt leer */ }
    }
  }

  const filtered = groups.filter(g => g.group_code.toLowerCase().includes(search.toLowerCase()))

  return (
    <>
      <Nav />
      <main className="pt-28 pb-20 px-8 max-w-5xl mx-auto">
        <div className="mb-12">
          <p className="text-xs tracking-widest uppercase mb-3" style={{ color: 'var(--muted)' }}>
            {text.eyebrow}
          </p>
          <h1 className="font-display text-5xl leading-none flex items-center gap-4">
            <NotionIcon name="dashboard" size={44} />
            {text.title}
          </h1>
        </div>

        <TeacherIntro
          storageKey="toadapt_intro_dashboard_v1"
          title={text.introTitle}
          steps={text.introSteps}
          hint={text.introHint}
          dismissLabel={text.introDismiss}
        />

        <div className="divider mb-10" />

        {overview && (
          <>
            {/* KPIs */}
            <p className="mb-3 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
              KPIs
              <HelpHint text={text.helpKpis} />
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-6 mb-12">
              {[
                { label: text.students, value: overview.total_students, icon: <Users size={14} /> },
                { label: text.submissions, value: overview.total_submissions, icon: <TrendingUp size={14} /> },
                { label: text.averageScore, value: `${overview.avg_percentage.toFixed(0)}%`, icon: null },
                { label: text.averageCanvas, value: `${overview.avg_canvas_alignment_pct.toFixed(0)}%`, icon: null },
                { label: text.exemplars, value: overview.exemplar_submissions_count, icon: null },
                {
                  label: text.reviewFallback,
                  value: `${overview.needs_human_review_count}/${overview.technical_fallback_count}`,
                  icon: null,
                },
              ].map(k => (
                <div
                  key={k.label}
                  className="h-32 p-6 flex flex-col justify-between"
                  style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.12)' }}
                >
                  <div className="min-h-9 flex items-start gap-2" style={{ color: 'var(--muted)' }}>
                    {k.icon}
                    <span className="text-xs tracking-widest uppercase leading-snug">{k.label}</span>
                  </div>
                  <p className="font-display text-4xl leading-none tabular-nums">{k.value}</p>
                </div>
              ))}
            </div>

            {/* Bloom + TP breakdown */}
            <div className="grid grid-cols-2 gap-10 mb-14">
              <div>
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>{text.byBloom}<HelpHint text={text.helpBloom} /></p>
                <div className="flex flex-col gap-3">
                  {Object.entries(overview.by_bloom).map(([lvl, pct]) => (
                    <MiniBar key={lvl} pct={pct} label={BLOOM[language][Number(lvl)] ?? `Bloom ${lvl}`} />
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>{text.byTp}</p>
                <div className="flex flex-col gap-3">
                  {Object.entries(overview.by_tp).map(([tp, pct]) => (
                    <MiniBar key={tp} pct={pct} label={`TP ${tp}`} />
                  ))}
                </div>
              </div>
            </div>

            {/* Weakest learning objectives (Kohorte) */}
            {overview.top_objectives.length > 0 && (
              <div className="mb-14 p-6" style={{ background: 'var(--surface)', border: '1px solid rgba(53,40,30,0.12)' }}>
                <p className="text-xs tracking-widest uppercase mb-5" style={{ color: 'var(--muted)' }}>{text.weakestObjectives}<HelpHint text={text.helpObjectives} /></p>
                <div className="flex flex-col gap-3">
                  {overview.top_objectives.map(o => (
                    <div key={o.tag} className="flex items-center justify-between">
                      <span className="text-sm">{objectiveLabel(o.tag)}</span>
                      <div className="flex items-center gap-4">
                        <span className="text-xs" style={{ color: 'var(--muted)' }}>n={o.n}</span>
                        <span className="text-sm font-medium" style={{ color: o.avg_pct < 50 ? '#c0392b' : 'var(--ink)' }}>
                          {o.avg_pct.toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Gruppen */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="flex items-center gap-2 text-xs tracking-widest uppercase" style={{ color: 'var(--muted)' }}>
              <NotionIcon name="groups" size={24} />
              {text.groups(filtered.length)}
              <HelpHint text={text.helpGroups} />
            </p>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={text.searchPlaceholder}
              className="px-3 py-1.5 text-sm bg-transparent outline-none"
              style={{ border: '1px solid rgba(53,40,30,0.2)', color: 'var(--ink)', width: '220px' }}
            />
          </div>
          <p className="text-xs mb-6" style={{ color: 'var(--muted)' }}>{text.groupHint}</p>

          <div className="divider" />
          {filtered.length === 0 ? (
            <p className="py-10 text-sm text-center" style={{ color: 'var(--muted)' }}>{text.noData}</p>
          ) : (
            filtered.map(g => {
              const open = expanded === g.group_code
              const detail = details[g.group_code]
              return (
                <div key={g.group_code}>
                  <button
                    onClick={() => toggleGroup(g.group_code)}
                    className="w-full flex items-center justify-between py-4 px-2 text-left"
                  >
                    <div className="flex items-center gap-4 flex-wrap">
                      <span className="font-mono text-sm font-medium">
                        {g.group_code === UNGROUPED ? text.ungrouped : g.group_code}
                      </span>
                      <span className="text-xs" style={{ color: 'var(--muted)' }}>
                        {text.members(g.members_active)} · {g.submissions_count} Sub.
                      </span>
                      {g.attention_high > 0 && (
                        <span className="text-xs px-2 py-0.5" style={{ background: 'rgba(192,57,43,0.1)', color: '#c0392b' }}>
                          {g.attention_high} {text.needsAttention}
                        </span>
                      )}
                      {g.attention_medium > 0 && (
                        <span className="text-xs px-2 py-0.5" style={{ background: 'rgba(173,63,43,0.08)', color: '#ad3f2b' }}>
                          {g.attention_medium} {text.watch}
                        </span>
                      )}
                    </div>
                    <span className="text-sm font-medium shrink-0" style={{ color: g.avg_percentage >= 70 ? 'var(--accent)' : g.avg_percentage < 45 ? '#c0392b' : 'var(--ink)' }}>
                      Ø {g.avg_percentage.toFixed(0)}%
                    </span>
                  </button>

                  {open && detail && (
                    <div className="px-2 pb-5 flex flex-col gap-3">
                      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs" style={{ color: 'var(--muted)' }}>
                        <span>{text.review}: {detail.needs_human_review_count}/{detail.technical_fallback_count}</span>
                        {detail.paste_heavy_answers > 0 && (
                          <span style={{ color: '#ad3f2b' }}>{text.pasteHint(detail.paste_heavy_answers)}</span>
                        )}
                      </div>

                      {detail.weak_objectives.filter(o => o.members_below > 0).length > 0 && (
                        <div>
                          <p className="text-xs font-medium mb-1">{text.weakObjectives}</p>
                          {detail.weak_objectives.filter(o => o.members_below > 0).map(o => (
                            <p key={o.tag} className="text-xs leading-5" style={{ color: 'var(--muted)' }}>
                              {objectiveLabel(o.tag)} — {text.membersBelow(o.members_below, o.members_total)} · Ø {o.avg_pct.toFixed(0)}%
                            </p>
                          ))}
                        </div>
                      )}

                      {Object.keys(detail.weak_blooms).length > 0 && (
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>
                          {text.weakBlooms}: {Object.entries(detail.weak_blooms)
                            .map(([lvl, n]) => `${BLOOM[language][Number(lvl)] ?? `Bloom ${lvl}`} (${n})`)
                            .join(', ')}
                        </p>
                      )}

                      {detail.common_penalties.length > 0 && (
                        <div>
                          <p className="text-xs font-medium mb-1">{text.commonPenalties}</p>
                          {detail.common_penalties.map(p => (
                            <p key={p.text} className="text-xs leading-5" style={{ color: 'var(--muted)' }}>
                              – {p.text} {p.count > 1 && <span>×{p.count}</span>}
                            </p>
                          ))}
                        </div>
                      )}

                      {detail.missing_canvas_blocks.length > 0 && (
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>
                          {text.missingBlocks}: {detail.missing_canvas_blocks.map(b => `${objectiveLabel(b.text)} (×${b.count})`).join(', ')}
                        </p>
                      )}

                      {detail.weak_objectives.every(o => o.members_below === 0)
                        && detail.common_penalties.length === 0 && (
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>{text.noFindings}</p>
                      )}
                    </div>
                  )}
                  <div className="divider" />
                </div>
              )
            })
          )}
        </div>
      </main>
    </>
  )
}
