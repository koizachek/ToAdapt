"""Zeit-Hilfsfunktionen.

`datetime.utcnow()` ist ab Python 3.12 deprecated. `naive_utcnow()` liefert
denselben *naiven* UTC-Zeitstempel wie bisher (ohne tzinfo), damit bestehende
Vergleiche mit naiven Datetimes (z.B. datetime.min im Dashboard) nicht brechen.
"""

from datetime import datetime, timezone


def naive_utcnow() -> datetime:
    """Naiver UTC-Zeitstempel — verhaltensgleich zu datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
