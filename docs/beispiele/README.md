# Beispiele der Tutor-Pipeline (synthetisch, Stand 2026-09-02)

Alle Inhalte stammen aus den konstruierten Beispielabgaben der Kursleitung
(KI_Paket TP1) — keine echten Studierendendaten.

- `KI-Briefing_TP1_UEG01_Beispiel.docx` — Produkt 1: Briefing für die ÜGL,
  eine Übungsgruppe mit drei Stammgruppen (Anker überzeugend / tragfähig /
  ansatzweise), im Layout der Briefing-Vorlage der Kursleitung.
- `KI-Feedback_TP1-UEG01-SG2_Beispiel.docx` — Produkt 2: Rückmeldung an
  eine Stammgruppe (Anker tragfähig).
- `Pilot-Test_TP1_UEG01_UEG02.zip` — Test-Upload für den Master-Tutor: fünf
  PPTX aus der offiziellen Abgabevorlage (UEG01 SG1–3, UEG02 SG1–2).

Erzeugt mit `scripts/calibrate_briefings.py --tp 1 --feedback` (echter
LLM-Lauf) und `backend/briefings/docx_render.py`.
