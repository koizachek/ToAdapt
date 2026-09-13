"""Konten der Übungsgruppenleiter: Passwort-Prüfwerte, Reset-Anfragen, Einmalcodes.

Muster D3 (siehe toadapt-architecture-contract): Mongo primär, Datei-Fallback
write-through für die lokale Entwicklung; Fehler werden geloggt, crashen nie
den Request.

Gespeichert wird NIE ein Passwort im Klartext, sondern ein PBKDF2-HMAC-SHA256-
Prüfwert mit zufälligem Salt. Ein Einmalcode (vom Master erzeugt, 24 h
gültig) wird ebenfalls nur als Prüfwert abgelegt; beim Einlösen wird das
alte Passwort gelöscht und der Übungsgruppenleiter legt ein neues fest.

Ablauf (Owner-Entscheidung 2026-09-13):
  1. Erster Login: Konto ohne Passwort → Übungsgruppenleiter legt es fest.
  2. Passwort vergessen: Anfrage wird markiert (reset_requested_at); der
     Master sieht das im Monitoring, erzeugt einen Einmalcode und schickt
     ihn selbst per E-Mail. Login mit dem Einmalcode → neues Passwort.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import structlog

from backend.config import retention
from backend.config.tutor_accounts import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    RESET_CODE_TTL_HOURS,
    TUTOR_ACCOUNTS,
)
from backend.db import mongo
from backend.timeutils import naive_utcnow

logger = structlog.get_logger(__name__)

ACCOUNTS_DIR = Path(__file__).resolve().parent / "tutor_accounts"
ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)

PBKDF2_ITERATIONS = 200_000
_RESET_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # keine 0/O, 1/l/I

VerifyResult = Literal["ok", "set_password", "reset_code", "wrong", "unknown"]


class PasswordPolicyError(ValueError):
    pass


def check_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Das Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen haben.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Das Passwort darf höchstens {MAX_PASSWORD_LENGTH} Zeichen haben.")


def hash_secret(secret: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_secret(secret: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iterations, salt_b64, digest_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, int(iterations))
    return hmac.compare_digest(candidate, expected)


def make_reset_code() -> str:
    chunk = lambda: "".join(secrets.choice(_RESET_CODE_ALPHABET) for _ in range(4))  # noqa: E731
    return f"{chunk()}-{chunk()}-{chunk()}"


def _empty_account(account: str) -> dict[str, Any]:
    return {
        "account": account,
        "password_hash": None,
        "password_set_at": None,
        "last_login_at": None,
        "reset_requested_at": None,
        "reset_code_hash": None,
        "reset_code_expires_at": None,
        "reset_code_issued_at": None,
    }


class TutorAccountStore:
    def __init__(self) -> None:
        self.collection_name = os.environ.get("MONGODB_TUTOR_ACCOUNTS_COLLECTION", "tutor_accounts")

    # -- Persistenz -------------------------------------------------------

    def _save(self, record: dict[str, Any]) -> None:
        account = str(record["account"])
        (ACCOUNTS_DIR / f"{account}.json").write_text(
            json.dumps(record, default=str, ensure_ascii=False), encoding="utf-8"
        )
        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            return
        doc = json.loads(json.dumps(record, default=str))
        doc[retention.TTL_FIELD] = retention.formative_expire_at()
        try:
            collection.replace_one({"account": account}, doc, upsert=True)
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("tutor_account_save_failed", account=account, error=str(exc))

    def _load_all(self) -> dict[str, dict[str, Any]]:
        collection = mongo.get_collection(self.collection_name)
        if collection is not None:
            try:
                docs = list(collection.find({}, {"_id": 0, retention.TTL_FIELD: 0}))
                if docs:
                    return {str(d.get("account")): d for d in docs}
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("tutor_account_load_failed", error=str(exc))
        out: dict[str, dict[str, Any]] = {}
        for f in ACCOUNTS_DIR.glob("*.json"):
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
                out[str(doc.get("account"))] = doc
            except Exception:
                pass
        return out

    def get(self, account: str) -> dict[str, Any] | None:
        if account not in TUTOR_ACCOUNTS:
            return None
        return self._load_all().get(account) or _empty_account(account)

    def list_all(self) -> list[dict[str, Any]]:
        stored = self._load_all()
        return [stored.get(a) or _empty_account(a) for a in TUTOR_ACCOUNTS]

    # -- Sicht ohne Geheimnisse --------------------------------------------

    @staticmethod
    def public_view(record: dict[str, Any]) -> dict[str, Any]:
        expires = record.get("reset_code_expires_at")
        active = bool(record.get("reset_code_hash")) and _not_expired(expires)
        return {
            "account": record["account"],
            "password_set": bool(record.get("password_hash")),
            "password_set_at": record.get("password_set_at"),
            "last_login_at": record.get("last_login_at"),
            "reset_requested_at": record.get("reset_requested_at"),
            "reset_code_active": active,
            "reset_code_expires_at": expires if active else None,
        }

    # -- Fachlogik ---------------------------------------------------------

    def verify(self, account: str, password: str) -> VerifyResult:
        """Login-Prüfung. 'set_password' = Konto hat (noch) kein Passwort;
        'reset_code' = gültiger Einmalcode eingelöst, altes Passwort gelöscht,
        neues muss gesetzt werden."""
        record = self.get(account)
        if record is None:
            return "unknown"
        if record.get("reset_code_hash") and _not_expired(record.get("reset_code_expires_at")):
            if verify_secret(password, record["reset_code_hash"]):
                record["password_hash"] = None
                record["password_set_at"] = None
                record["reset_code_hash"] = None
                record["reset_code_expires_at"] = None
                record["reset_requested_at"] = None
                self._save(record)
                logger.info("tutor_reset_code_consumed", account=account)
                return "reset_code"
        if not record.get("password_hash"):
            return "set_password"
        if verify_secret(password, record["password_hash"]):
            record["last_login_at"] = naive_utcnow().isoformat()
            self._save(record)
            return "ok"
        return "wrong"

    def set_password(self, account: str, password: str) -> bool:
        """Setzt das Passwort NUR, wenn das Konto keins hat (erster Login oder
        nach eingelöstem Einmalcode). False, wenn bereits eins existiert."""
        check_password_policy(password)
        record = self.get(account)
        if record is None:
            raise KeyError(account)
        if record.get("password_hash"):
            return False
        now = naive_utcnow().isoformat()
        record["password_hash"] = hash_secret(password)
        record["password_set_at"] = now
        record["last_login_at"] = now
        record["reset_requested_at"] = None
        record["reset_code_hash"] = None
        record["reset_code_expires_at"] = None
        self._save(record)
        logger.info("tutor_password_set", account=account)
        return True

    def request_reset(self, account: str) -> bool:
        record = self.get(account)
        if record is None:
            return False
        record["reset_requested_at"] = naive_utcnow().isoformat()
        self._save(record)
        logger.info("tutor_reset_requested", account=account)
        return True

    def issue_reset_code(self, account: str, *, issued_by: str | None) -> tuple[str, str] | None:
        """Erzeugt einen Einmalcode (Klartext wird EINMAL zurückgegeben) und
        speichert nur den Prüfwert. Rückgabe (code, expires_at_iso)."""
        record = self.get(account)
        if record is None:
            return None
        code = make_reset_code()
        expires = (naive_utcnow() + timedelta(hours=RESET_CODE_TTL_HOURS)).isoformat()
        record["reset_code_hash"] = hash_secret(code)
        record["reset_code_expires_at"] = expires
        record["reset_code_issued_at"] = naive_utcnow().isoformat()
        self._save(record)
        logger.info("tutor_reset_code_issued", account=account, by=issued_by)
        return code, expires


def _not_expired(iso: Any) -> bool:
    if not iso:
        return False
    try:
        return datetime.fromisoformat(str(iso)) > naive_utcnow()
    except ValueError:
        return False


tutor_account_store = TutorAccountStore()
