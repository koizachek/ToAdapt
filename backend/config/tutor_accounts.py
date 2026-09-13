"""Feste Konten der Übungsgruppenleiter (Owner-Entscheidung 2026-09-13).

26 Konten UEGL01 bis UEGL26 plus Testkonto UEGL00. Die Passwörter legen die Übungsgruppenleiter
beim ersten Login selbst fest (mindestens MIN_PASSWORD_LENGTH Zeichen);
gespeichert wird nur ein PBKDF2-Prüfwert (backend/db/tutor_account_store.py).
Der Master-Login bleibt der Code aus TEACHER_ARCHIVE_CODE (Frontend-Env).
"""

from __future__ import annotations

import re

TUTOR_ACCOUNT_COUNT = 26
TEST_ACCOUNT = "UEGL00"   # Testkonto der Kursleitung (Owner-Entscheidung 2026-09-13)
TUTOR_ACCOUNTS: tuple[str, ...] = (TEST_ACCOUNT, *(f"UEGL{i:02d}" for i in range(1, TUTOR_ACCOUNT_COUNT + 1)))
MASTER_ACCOUNT = "master"

MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128
RESET_CODE_TTL_HOURS = 24

_ACCOUNT_RE = re.compile(r"^\s*UEGL\s*0*(\d{1,2})\s*$", re.IGNORECASE)


def normalize_account(value: str | None) -> str:
    """'uegl5' / 'UEGL05' / ' UEGL 5 ' → 'UEGL05'; '' wenn kein gültiges Konto."""
    match = _ACCOUNT_RE.match(str(value or ""))
    if not match:
        return ""
    account = f"UEGL{int(match.group(1)):02d}"
    return account if account in TUTOR_ACCOUNTS else ""
