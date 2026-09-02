"""KI-Briefings für Übungsgruppenleitungen (ÜGL).

Pipeline: Master-Upload (ZIP mit Stammgruppen-Abgaben aus Canvas) →
Extraktion (PPTX/DOCX/PDF, Kenndaten, Zeichenzählung) → Briefing-Generator
(LLM, Rubric je Touchpoint) → Leitplanken-Nachprüfung → Store → DOCX-Download
je Übungsgruppe. Grundlage: KI_Paket / ki_rubrics_tp{n}.json der Kursleitung
BWL A HS26 (Stand 2026-08-28).
"""
