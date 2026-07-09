"""TP-Konfigurationen und globaler TP-Stundenplan."""

from datetime import date

TP_SCHEDULE: dict[int, dict[str, date]] = {
    1: {"start": date(2026, 9, 14),  "deadline": date(2026, 10, 5)},
    2: {"start": date(2026, 10, 6),  "deadline": date(2026, 10, 26)},
    3: {"start": date(2026, 10, 27), "deadline": date(2026, 11, 16)},
    4: {"start": date(2026, 11, 17), "deadline": date(2026, 12, 7)},
}


def current_tp_phase(today: date | None = None) -> int:
    """Gibt die aktuell aktive TP-Phase zurück (1–4).

    Außerhalb aller Phasen wird 1 als Fallback zurückgegeben.
    """
    d = today or date.today()
    for tp, window in TP_SCHEDULE.items():
        if window["start"] <= d <= window["deadline"]:
            return tp
    # Vor Kursbeginn → TP1; nach Kursende → TP4
    if d < TP_SCHEDULE[1]["start"]:
        return 1
    return 4


TP_CONFIGS: dict[int, dict] = {
    1: {
        "name": "Analyse & Stakeholder",
        "bloom_levels": [2, 3, 4],
        "format": "3 Slides (PDF)",
        "allowed_frameworks": [
            "SGMM (Umwelt-Organisation-Spannungsfeld)",
            "Stakeholder-Mapping (Einfluss/Betroffenheit)",
        ],
        "forbidden_framework_names": [
            "Porter", "RBV", "Five Forces", "VRIO",
            "Transaktionskosten", "Preiselastizität",
        ],
        "case_chapters": ["A"],
        "key_questions": [
            "Welche Herausforderungen sind am kritischsten?",
            "Wo liegt das Spannungsfeld Umwelt ↔ Organisation?",
            "Welcher Stakeholder hat den höchsten Einfluss?",
        ],
        "rubric_reference": "tp1_rubric.json",
        "max_slides": 3,
        "max_bullets_per_slide": 6,
        "individual_component": {
            "question": "Was würdest du an deiner eigenen Analyse konkret verändern – und warum?",
            "points": 6,
            "time_minutes": 5,
        },
    },
    2: {
        "name": "Strategische Entscheidung",
        "bloom_levels": [4, 5],
        "format": "Management-Memo (1 Seite, PDF)",
        "allowed_frameworks": [
            "SGMM", "Stakeholder-Mapping",
            "Wettbewerbslogik (Kosten vs. Differenzierung)",
            "Ressourcenbasierte Logik (VRIO-Prinzip, ohne Namen)",
            "KPI und Steuerungslogik",
        ],
        "forbidden_framework_names": [
            "Porter", "Five Forces", "RBV", "VRIO",
            "Transaktionskosten", "Preiselastizität", "4P", "Marketing-Mix",
        ],
        "case_chapters": ["A", "B"],
        "requires_tp1_reference": True,
        "key_questions": [
            "Wie soll ON wachsen?",
            "Worauf basiert der Wettbewerbsvorteil?",
            "Welcher Trade-off wird bewusst eingegangen?",
            "Welche Kennzahl misst den Erfolg?",
        ],
        "rubric_reference": "tp2_rubric.json",
        "individual_component": {
            "question": "Welche Entscheidung würdest du anders treffen?",
            "points": 8,
            "time_minutes": 5,
        },
    },
    3: {
        "name": "Strategie in den Markt übersetzen",
        "bloom_levels": [3, 4, 5],
        "format": "Decision Log (max. 2 Seiten A4, PDF)",
        "allowed_frameworks": [
            "Alle aus TP1+TP2",
            "Preiselastizität (implizit)",
            "Marketing-Mix (implizit)",
            "Transaktionskostenlogik (implizit)",
        ],
        "forbidden_framework_names": [
            "Preiselastizität", "4P", "Marketing-Mix",
            "Transaktionskostentheorie", "TCE",
        ],
        "case_chapters": ["A", "B", "C"],
        "requires_tp2_reference": True,
        "decision_fields": [
            "Preisstrategie",
            "Kommunikation & Positionierung",
            "Make-or-Buy",
            "Digitalisierung & Prozesse",
        ],
        "key_questions": [
            "Wie hängt diese Preisentscheidung mit eurer TP2-Strategie zusammen?",
            "Worauf verzichtet ON mit dieser Preispositionierung bewusst?",
            "Welche Kundengruppen werden nicht angesprochen?",
            "Sind eure vier Entscheidungen untereinander konsistent?",
        ],
        "rubric_reference": "tp3_rubric.json",
        "individual_component": {
            "question": "Wo weicht die Umsetzung am stärksten von der Strategie ab?",
            "points": 8,
            "time_minutes": 5,
        },
    },
    4: {
        "name": "Integration & Gesamtbild",
        "bloom_levels": [5, 6],
        "format": "Strategy-on-a-Page (1 Seite, visuell + Text)",
        "allowed_frameworks": [
            "Alle aus TP1–TP3",
            "Geschäftsmodell-Logik (Wertversprechen, Wertschöpfung, Erlös)",
            "SGMM-Gestaltungsdimensionen (Strategie, Struktur, Kultur, Prozesse)",
        ],
        "case_chapters": ["A", "B", "C", "D"],
        "requires_tp123_reference": True,
        "areas": [
            "Strategische Priorisierung (5 Pkt)",
            "Geschäftsmodell-Charakterisierung (5 Pkt)",
            "Gestaltungsdimensionen + Wechselwirkungen (4 Pkt)",
            "Risiken (optional, +3 Bonus)",
        ],
        "key_questions": [
            "Wie hängen TP1-Analyse, TP2-Strategie und TP3-Umsetzung zusammen?",
            "Welche Gestaltungsdimensionen verändern sich am stärksten?",
            "Was passiert, wenn eure riskanteste Entscheidung scheitert?",
            "Wo auf der Seite zeigt ihr Systemverständnis?",
        ],
        "rubric_reference": "tp4_rubric.json",
        "individual_component": {
            "question": "Riskanteste Entscheidung + Revisionskonsequenz (Kaskadeneffekt)",
            "points": 10,
            "time_minutes": 10,
        },
    },
}
