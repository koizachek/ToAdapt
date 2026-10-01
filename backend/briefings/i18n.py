"""Sprache der KI-Briefings (Owner-Entscheidung 2026-09-28).

Die Sprache der Abgabe bestimmt die Sprache des Briefings für diese
Stammgruppe: englische Abgabe → englisches Briefing, deutsche Abgabe →
deutsches Briefing. Die Sprache wird aus dem extrahierten Abgabetext erkannt
(``detect_language``) und am Datensatz gespeichert (``language``).

Im Sammeldokument einer Übungsgruppe steht jede Stammgruppe in ihrer
Sprache; Kopf und Einleitung sind deutsch, ausser alle Stammgruppen des
Dokuments haben englisch abgegeben (dann englisch — gilt auch für den
Einzel-Download eines englischen Briefings).

Englische Fassungen der Kursmaterialien: ``backend/config/ki_rubrics/en/``
(Rubrics) und ``backend/config/ki_rubrics/case/en/`` (ON-Case).

Hinweistexte, die die Pipeline selbst erzeugt (Extraktion, Eingangsprüfung,
formale Vorprüfung), entstehen deutsch, bevor die Sprache feststeht; für
englische Abschnitte übersetzt ``translate_note`` sie beim Rendern.
"""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["de", "en"]
LANGUAGES: tuple[str, ...] = ("de", "en")
DEFAULT_LANGUAGE: Language = "de"

# Häufige Funktionswörter — Inhaltswörter wären fallabhängig und würden
# durch Fallbegriffe (Exhibit, Premium, Stakeholder …) verfälscht.
_DE_WORDS = {
    "der", "die", "das", "und", "ist", "nicht", "mit", "sich", "auf", "für", "ein", "eine",
    "einen", "den", "dem", "des", "zu", "von", "wir", "sind", "wird", "werden", "auch",
    "als", "bei", "weil", "dass", "oder", "aber", "durch", "nach", "über", "unsere", "unser",
    "diese", "dieser", "noch", "nur", "wenn", "kann", "muss", "hat", "haben", "sie", "es",
}
_EN_WORDS = {
    "the", "and", "is", "are", "of", "to", "in", "that", "this", "with", "for", "not", "we",
    "our", "it", "as", "be", "by", "which", "because", "or", "but", "from", "its", "their",
    "has", "have", "can", "must", "will", "would", "should", "on", "at", "an", "these",
    "than", "more", "if", "only", "also", "they", "was", "were", "does",
}
_WORD = re.compile(r"[a-zäöüß]+", re.IGNORECASE)


def detect_language(text: str) -> Language:
    """``en``, wenn englische Funktionswörter klar überwiegen; sonst ``de``
    (auch bei leerem oder zu kurzem Text — Kurs-Standard)."""
    words = [w.lower() for w in _WORD.findall(text or "")]
    de = sum(1 for w in words if w in _DE_WORDS)
    en = sum(1 for w in words if w in _EN_WORDS)
    if en >= 5 and en > de * 1.5:
        return "en"
    return "de"


def normalize_language(value: object) -> Language:
    return "en" if str(value or "").strip().lower() == "en" else "de"


# ---------------------------------------------------------------------------
# Texte des Generators (tutor-sichtbar im Briefing)
# ---------------------------------------------------------------------------

NO_CONTENT_TEXT: dict[str, str] = {
    "de": "Zu diesem Baustein liegt kein Text vor.",
    "en": "There is no text for this building block.",
}
FALLBACK_TEXT: dict[str, str] = {
    "de": "Die automatische Verdichtung konnte technisch nicht erstellt werden — bitte die Abgabe direkt lesen.",
    "en": "The automatic summary could not be created for technical reasons — please read the submission directly.",
}
GUARDRAIL_PLACEHOLDER: dict[str, str] = {
    "de": "[Von der Leitplanken-Prüfung zurückgehalten — bitte die Abgabe direkt lesen.]",
    "en": "[Withheld by the guardrail check — please read the submission directly.]",
}
REVIEW_TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "few_questions": "Weniger Beispiel-Rückfragen als vorgesehen.",
        "guardrail": "Leitplanken-Prüfung hat Textteile zurückgehalten: ",
        "no_text": "Kein Text in der Abgabe gefunden.",
        "llm_failed": "LLM-Aufruf fehlgeschlagen.",
        "json_failed": "Modellantwort war auch nach Reparaturversuch kein valides JSON.",
        "wrong_language": "Das Modell hat nicht in der Sprache der Abgabe geantwortet — bitte prüfen.",
    },
    "en": {
        "few_questions": "Fewer example follow-up questions than intended.",
        "guardrail": "The guardrail check withheld parts of the text: ",
        "no_text": "No text found in the submission.",
        "llm_failed": "The model call failed.",
        "json_failed": "The model response was not valid JSON even after a repair attempt.",
        "wrong_language": "The model did not answer in the language of the submission — please check.",
    },
}

# Sprachanweisung im System-Prompt (ersetzt die Zeile "Sprache: …").
PROMPT_LANGUAGE_RULE: dict[str, str] = {
    "de": "- Sprache: Schweizer Standarddeutsch (ss statt ß), sachlich, knapp, ganze Sätze.",
    "en": (
        "- Sprache: Die Gruppe hat auf Englisch abgegeben. Schreibe ALLE Textfelder des JSON auf Englisch "
        "(British English), sachlich, knapp, ganze Sätze. Wörtliche Zitate aus der Abgabe bleiben wörtlich. "
        "Orte heissen \"slide 2\", \"slide 3\", Fallstellen \"Section 2.8\", \"Exhibit A6\". "
        "Die JSON-Schlüssel und die Niveau-Werte (ueberzeugend | tragfaehig | ansatzweise) bleiben unverändert."
    ),
}

# Sprachvorgabe am Anfang des System-Prompts und am Ende der Abgabe-Nachricht:
# Eine einzelne Zeile im deutschen Prompt reichte nicht, das Modell schrieb
# englische Abgaben deutsch (Test 2026-09-29).
PROMPT_LANGUAGE_HEADER: dict[str, str] = {
    "de": "",
    "en": (
        "OUTPUT LANGUAGE: ENGLISH. The group submitted in English. Every text value of the JSON you "
        "return must be written in English (British English), even though these instructions are in "
        "German. Never write German. JSON keys and niveau values stay unchanged.\n\n"
    ),
}
USER_LANGUAGE_REMINDER: dict[str, str] = {
    "de": "Erstelle jetzt das JSON. Alle Textfelder auf Deutsch.",
    "en": "Now write the JSON. Every text value in English — no German.",
}
# Dünne Stelle aus der Fallprüfung: Aussage der Gruppe, die dem Fall widerspricht.
MISREADING_TEMPLATE: dict[str, str] = {
    "de": "Wiedergabe des Falls: Die Gruppe schreibt «{aussage}». {fallstelle}: {im_fall} Worauf stützt die Gruppe ihre Lesart?",
    "en": "Reading of the case: The group writes “{aussage}”. {fallstelle}: {im_fall} What does the group base its reading on?",
}
LANGUAGE_RETRY_PROMPT: dict[str, str] = {
    "de": (
        "Deine Antwort ist nicht auf Deutsch. Die Gruppe hat auf Deutsch abgegeben. Gib dasselbe "
        "JSON noch einmal aus, alle Textfelder auf Deutsch (Schweizer Standarddeutsch). Nur das JSON."
    ),
    "en": (
        "Your answer is not in English. The group submitted in English. Return the same JSON again "
        "with every text value written in English (British English). Keys and niveau values unchanged. "
        "Only the JSON."
    ),
}

# Ausblick je Touchpoint, englische Fassung von rubrics.FEED_FORWARD.
FEED_FORWARD_EN: dict[int, str] = {
    1: "In Touchpoint 2 the decision is built on this analysis; in the exam this is Task 1 on an unknown case.",
    2: "In Touchpoint 3 market entry is measured against today's strategy; in the exam this is Task 2 on an unknown case.",
    3: "Touchpoint 4 is about make or buy and the supply chain; in the exam this is Task 3, there with an opposite margin-versus-control constellation.",
    4: "In Touchpoint 5 all decisions are checked for consistency; in the exam this is Task 4 on a company with a different business model, where control carries different weight.",
    5: "In the exam this is Task 5, the largest block; the case changes, the thinking operations remain.",
}


# ---------------------------------------------------------------------------
# Feste Texte des Word-Dokuments
# ---------------------------------------------------------------------------

DOC_LABELS: dict[str, dict[str, str]] = {
    "de": {
        "kicker": "KI-Briefing",
        "title": "Touchpoint {tp} · Übungsgruppe {ueg}",
        "no_ueg": "ohne Zuordnung",
        "title_sg": " · Stammgruppe SG{sg}",
        "meta": (
            "BWL A Assessment-Jahr HS26 · Running Case ON, Kapitel {chapter} · Abgabe {abgabe} · "
            "Termin {termin} · Klausurbezug {exam} · Rubric {version} vom {date}"
        ),
        "intro": (
            "Nur für die Übungsgruppenleitung. Dieses Briefing verdichtet jede Abgabe entlang der "
            "Bausteine des Arbeitsauftrags: Kernposition, tragende Argumente, dünne Stellen. Es enthält "
            "keine Punkte, keine Stufen und keine Musterlösung — jede Wahl ist zulässig, beurteilt wird "
            "nur, ob die Begründung trägt. Die Wahl der Spannungslinie und der Rückfragen bleibt Ihre "
            "didaktische Entscheidung."
        ),
        "outlook": "Ausblick:",
        "footer": "Automatisch erstellt durch ToAdapt · KI-Pipeline BWL A HS26",
        "place_date": "St.Gallen, {date}",
        "group": "Stammgruppe SG{sg}",
        "group_unassigned": "Stammgruppe (nicht zugeordnet)",
        "row_canvas_group": "Canvas-Gruppe",
        "extraction_failed": "Die Datei konnte nicht gelesen werden — bitte die Abgabe direkt öffnen. ",
        "rejected": "Abgelehnt — kein Briefing: ",
        "injection": "Achtung: Die Gruppe hat versucht, eine Prompt-Injection einzugeben.",
        "injection_found": "Gefundener Text: „{excerpt}“",
        "review_default": "Automatische Verdichtung mit Vorbehalt.",
        "review": "Hinweis: {reason}",
        "formal_heading": "Formale Vorprüfung (gemeldet, nicht bewertet)",
        "baustein_heading": "Baustein {n} · {title} (Folie {slide}, Klausur {exam})",
        "kernposition": "Kernposition:",
        "argumente": "Tragende Argumente:",
        "argumente_none": "Keine tragenden Argumente identifiziert.",
        "duenn": "Dünne Stellen (Ansatz für Rückfragen):",
        "duenn_none": "Keine dünnen Stellen identifiziert.",
        "einschaetzung": "Einschätzung:",
        "naechster_schritt": "Nächster Schritt:",
        "questions_heading": "Beispiel-Rückfragen an die Gruppe",
        "questions_intro": "Vorschläge für das Gespräch — welche Fragen Sie stellen, bleibt Ihre didaktische Entscheidung.",
        "questions_strengths": "An die Stärken anknüpfen:",
        "questions_weaknesses": "Dünne Stellen aufdecken:",
        "questions_none": "Keine Vorschläge.",
        "slide_row": "Folie {slide} (Baustein {n})",
        "chars": "{chars} von {limit} Zeichen · {status}",
        "within": "innerhalb der Grenze",
        "over": "über der Grenze (+{n})",
        "row_group": "Gruppe",
        "group_code": "Touchpoint {tp} · Übungsgruppe {ueg} · Stammgruppe {sg}",
        "tp_mismatch": " · Touchpoint auf dem Deckblatt weicht ab",
        "code_missing": "auf dem Deckblatt nicht erkennbar — bitte nachtragen",
        "row_filename": "Dateiname",
        "row_format": "Format",
        "official_template": " · offizielle Vorlage",
        "page": "Seite",
    },
    "en": {
        "kicker": "AI briefing",
        "title": "Touchpoint {tp} · Tutorial group {ueg}",
        "no_ueg": "unassigned",
        "title_sg": " · Home group SG{sg}",
        "meta": (
            "BWL A assessment year HS26 · Running Case ON, Chapter {chapter} · Submission {abgabe} · "
            "Session {termin} · Exam reference {exam} · Rubric {version} of {date}"
        ),
        "intro": (
            "For the tutorial group lead only. This briefing condenses each submission along the "
            "building blocks of the assignment: core position, supporting arguments, thin spots. It contains "
            "no points, no levels and no model solution — any choice is admissible; what is judged is only "
            "whether the reasoning holds. Choosing the line of tension and the follow-up questions remains "
            "your didactic decision."
        ),
        "outlook": "Outlook:",
        "footer": "Generated automatically by ToAdapt · AI pipeline BWL A HS26",
        "place_date": "St.Gallen, {date}",
        "group": "Home group SG{sg}",
        "group_unassigned": "Home group (unassigned)",
        "row_canvas_group": "Canvas group",
        "extraction_failed": "The file could not be read — please open the submission directly. ",
        "rejected": "Rejected — no briefing: ",
        "injection": "Warning: the group tried to enter a prompt injection.",
        "injection_found": "Text found: “{excerpt}”",
        "review_default": "Automatic summary with reservations.",
        "review": "Note: {reason}",
        "formal_heading": "Formal pre-check (reported, not graded)",
        "baustein_heading": "Building block {n} · {title} (slide {slide}, exam {exam})",
        "kernposition": "Core position:",
        "argumente": "Supporting arguments:",
        "argumente_none": "No supporting arguments identified.",
        "duenn": "Thin spots (prompts for follow-up questions):",
        "duenn_none": "No thin spots identified.",
        "einschaetzung": "Assessment:",
        "naechster_schritt": "Next step:",
        "questions_heading": "Example follow-up questions for the group",
        "questions_intro": "Suggestions for the discussion — which questions you ask remains your didactic decision.",
        "questions_strengths": "Building on strengths:",
        "questions_weaknesses": "Uncovering thin spots:",
        "questions_none": "No suggestions.",
        "slide_row": "Slide {slide} (building block {n})",
        "chars": "{chars} of {limit} characters · {status}",
        "within": "within the limit",
        "over": "over the limit (+{n})",
        "row_group": "Group",
        "group_code": "Touchpoint {tp} · tutorial group {ueg} · home group {sg}",
        "tp_mismatch": " · touchpoint on the cover sheet differs",
        "code_missing": "not recognisable on the cover sheet — please add",
        "row_filename": "File name",
        "row_format": "Format",
        "official_template": " · official template",
        "page": "Page",
    },
}

_MONTHS = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni",
           "Juli", "August", "September", "Oktober", "November", "Dezember"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
}


def format_date_long(day: int, month: int, year: int, language: str) -> str:
    if language == "en":
        return f"{day} {_MONTHS['en'][month - 1]} {year}"
    return f"{day}. {_MONTHS['de'][month - 1]} {year}"


# ---------------------------------------------------------------------------
# Hinweistexte der Pipeline (deutsch erzeugt) → englisch beim Rendern
# ---------------------------------------------------------------------------

_NOTE_TRANSLATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Abgabe hat (\d+) Folien \(Vorlage: 3\); nur Folie 2 und 3 wurden gelesen\."),
     r"The submission has \1 slides (template: 3); only slides 2 and 3 were read."),
    (re.compile(r"Abgabe hat (\d+) Folien \(Vorlage: 3\); Folie ([\d–]+) als Baustein 1, Folie ([\d–]+) als Baustein 2 gelesen — bitte prüfen\."),
     r"The submission has \1 slides (template: 3); slide \2 read as building block 1, slide \3 as building block 2 — please check."),
    (re.compile(r"Abgabe hat nur (\d+) Folie\(n\) \(Vorlage: 3\); Bausteine über Marker getrennt\."),
     r"The submission has only \1 slide(s) (template: 3); building blocks separated via markers."),
    (re.compile(r"Abgabe hat nur (\d+) Folie\(n\) \(Vorlage: 3\); Bausteine konnten nicht getrennt werden\."),
     r"The submission has only \1 slide(s) (template: 3); building blocks could not be separated."),
    (re.compile(r"PDF hat (\d+) Seiten \(Vorlage: 3\); nur Seite 2 und 3 wurden gelesen\."),
     r"The PDF has \1 pages (template: 3); only pages 2 and 3 were read."),
    (re.compile(r"Keine 'Baustein 1'/'Baustein 2'-Marker gefunden; der gesamte Text wurde Baustein 1 zugeordnet\."),
     "No 'Baustein 1'/'Baustein 2' markers found; the entire text was assigned to building block 1."),
    (re.compile(r"(baustein[12]): Text auf (\d+) Zeichen gekürzt\."),
     r"\1: text shortened to \2 characters."),
    (re.compile(r"Auf dem Deckblatt fehlen Touchpoint, Übungsgruppe oder Stammgruppe — bitte prüfen und nachtragen\."),
     "The cover sheet lacks touchpoint, tutorial group or home group — please check and add."),
    (re.compile(r"Keine 'Baustein 1'/'Baustein 2'-Abschnitte erkannt — der gesamte Text wurde als Baustein 1 gelesen\."),
     "No 'Baustein 1'/'Baustein 2' sections recognised — the entire text was read as building block 1."),
    (re.compile(r"Einer der beiden Bausteine ist leer\."), "One of the two building blocks is empty."),
    (re.compile(r"Die Gruppe hat versucht, eine Prompt-Injection einzugeben\."),
     "The group tried to enter a prompt injection."),
    (re.compile(r"Touchpoint (\d) aus dem Inhalt bestimmt\."), r"Touchpoint \1 determined from the content."),
    (re.compile(r"Touchpoint (\d) aus den übrigen Abgaben dieses Uploads übernommen\."),
     r"Touchpoint \1 taken from the other submissions of this upload."),
    (re.compile(r"Übungsgruppe (UEG\d+) aus den übrigen Abgaben dieses Uploads übernommen\."),
     r"Tutorial group \1 taken from the other submissions of this upload."),
    (re.compile(r"Stammgruppe SG(\d+) aus dem Dateinamen übernommen\."), r"Home group SG\1 taken from the file name."),
    (re.compile(r"(?:Folie 2 und 3|Die Antwortfolien) enthalten (\d+) (?:grosse\(s\) )?Bild\(er\) — Text in Bildern wurde nicht gelesen\."),
     r"The answer slides contain \1 large picture(s) — text inside pictures was not read."),
    (re.compile(r"Baustein (\d): Die Gruppe hat zusätzlich Text in das Notizenfeld unter der Folie geschrieben — "
                r"Notizen gehören nicht zur Abgabe und wurden nicht gelesen\."),
     r"Building block \1: the group also wrote text into the notes field below the slide — "
     r"notes are not part of the submission and were not read."),
    (re.compile(r"Baustein (\d): Die Gruppe hat nur ein Bild abgegeben — der Inhalt wurde nicht gelesen\."),
     r"Building block \1: the group submitted only a picture — its content was not read."),
    (re.compile(r"Baustein (\d): Die Gruppe hat einen Teil als Bild abgegeben — Text im Bild wurde nicht gelesen\."),
     r"Building block \1: the group submitted part of it as a picture — text inside the picture was not read."),
    (re.compile(r"Die Gruppe hat nur Bilder abgegeben, keinen Text — Text in Bildern wird nicht gelesen\. Die Gruppe muss die Antworten als Text einreichen\."),
     "The group submitted only pictures, no text — text inside pictures is not read. The group must submit its answers as text."),
    (re.compile(r"(\d+) Textfeld\(er\) ausserhalb der Folie oder unlesbar klein — nicht gelesen\."),
     r"\1 text box(es) outside the slide or unreadably small — not read."),
    (re.compile(r"Mehrere Abgaben dieses Uploads tragen dieselbe Stammgruppe — bitte Deckblätter prüfen und Zuordnung korrigieren\."),
     "Several submissions of this upload carry the same home group — please check the cover sheets and correct the assignment."),
    (re.compile(r"Das Deckblatt nennt Touchpoint (\d), ausgewertet wurde für Touchpoint (\d)\."),
     r"The cover sheet names touchpoint \1; the evaluation was done for touchpoint \2."),
    (re.compile(r"Touchpoint von (\d) auf (\d) geändert — die Auswertung wurde mit der Rubric von Touchpoint (\d) erstellt\."),
     r"Touchpoint changed from \1 to \2 — the evaluation was created with the rubric of touchpoint \3."),
    (re.compile(r"Themenprüfung technisch nicht möglich\."), "Topic check technically not possible."),
    (re.compile(r"Themenprüfung lieferte keine verwertbare Antwort\."), "The topic check returned no usable answer."),
    (re.compile(r"Themenprüfung nicht möglich\."), "Topic check not possible."),
    (re.compile(r"Versteckter Text \(ausserhalb der Folie\)"), "Hidden text (outside the slide)"),
    (re.compile(r"Versteckter Text \(winzige Schrift\)"), "Hidden text (tiny font)"),
    (re.compile(r"Versteckter Text \(weisse Schrift\)"), "Hidden text (white font)"),
    (re.compile(r"Weniger Beispiel-Rückfragen als vorgesehen\."), REVIEW_TEXTS["en"]["few_questions"]),
    (re.compile(r"Leitplanken-Prüfung hat Textteile zurückgehalten: "), REVIEW_TEXTS["en"]["guardrail"]),
]


def translate_note(text: str, language: str) -> str:
    """Übersetzt bekannte Pipeline-Hinweise; unbekannter Text bleibt, wie er ist."""
    if language != "en" or not text:
        return text
    out = str(text)
    for pattern, replacement in _NOTE_TRANSLATIONS:
        out = pattern.sub(replacement, out)
    return out
