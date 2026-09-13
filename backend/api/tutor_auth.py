"""Login der Übungsgruppenleiter (Konten UEGL01–UEGL26, selbst gewähltes Passwort).

Aufgerufen NUR vom Frontend-Server (Route-Handler /teacher-login) mit
X-API-Key — der Browser spricht diese Routen nie direkt an. Das Frontend
stellt nach erfolgreicher Prüfung das signierte Session-Cookie aus.

Ablauf:
  POST /auth/tutor/login          {account, password}
      → {"status": "ok"}             Passwort stimmt
      → {"status": "set_password", "reason": "first_login" | "reset_code"}
                                      Konto hat noch kein Passwort (erster
                                      Login: eingegebenes Passwort wird nur
                                      bestätigt) oder ein Einmalcode wurde
                                      eingelöst (neues Passwort festlegen)
      → 401                          falsches Passwort
      → 404                          unbekanntes Konto
  POST /auth/tutor/set-password   {account, password}  (nur wenn keins existiert)
  POST /auth/tutor/reset-request  {account}            (markiert die Anfrage;
                                                        der Master sieht sie)
  POST /auth/tutor/{account}/reset-code                (nur Master: erzeugt
                                                        einen Einmalcode, 24 h)
  GET  /auth/tutor/accounts                            (nur Master: Kontostatus
                                                        ohne Geheimnisse)

Der Master-Login selbst bleibt im Frontend (TEACHER_ARCHIVE_CODE).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.auth import reject_revoked_teacher_session, require_api_key
from backend.config.tutor_accounts import MAX_PASSWORD_LENGTH, TUTOR_ACCOUNTS, normalize_account
from backend.db.tutor_account_store import PasswordPolicyError, tutor_account_store
from backend.ratelimit import rate_limit

router = APIRouter(
    prefix="/auth/tutor",
    tags=["auth"],
    dependencies=[Depends(require_api_key), Depends(reject_revoked_teacher_session)],
)


class LoginRequest(BaseModel):
    account: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class SetPasswordRequest(BaseModel):
    account: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class ResetRequest(BaseModel):
    account: str = Field(min_length=1, max_length=32)


def _account_or_404(value: str) -> str:
    account = normalize_account(value)
    if not account:
        raise HTTPException(status_code=404, detail="Unbekanntes Konto (erwartet UEGL01 bis UEGL26)")
    return account


async def require_master_header(
    x_teacher_id: str | None = Header(default=None, alias="X-Teacher-Id"),
    x_teacher_master: str | None = Header(default=None, alias="X-Teacher-Master"),
) -> str | None:
    """Master-Routen: Header vom Teacher-Proxy (X-Teacher-Master=1) oder
    Operator-Aufruf ohne Identitäts-Header (Skript mit API-Key)."""
    if x_teacher_id is None and x_teacher_master is None:
        return None
    if (x_teacher_master or "").strip().lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Nur für den Master-Tutor")
    return (x_teacher_id or "").strip() or None


@router.post("/login", dependencies=[Depends(rate_limit(30, 60, scope="tutor_login"))])
async def login(body: LoginRequest) -> dict:
    account = _account_or_404(body.account)
    result = tutor_account_store.verify(account, body.password)
    if result == "unknown":
        raise HTTPException(status_code=404, detail="Unbekanntes Konto")
    if result == "wrong":
        raise HTTPException(status_code=401, detail="Passwort nicht korrekt")
    if result in ("set_password", "reset_code"):
        # reason: first_login = Konto hatte noch nie ein Passwort → das eben
        # eingegebene gilt und wird nur bestätigt; reset_code = Einmalcode
        # eingelöst → komplett neues Passwort festlegen.
        return {"status": "set_password", "account": account,
                "reason": "reset_code" if result == "reset_code" else "first_login"}
    return {"status": "ok", "account": account}


@router.post("/set-password", dependencies=[Depends(rate_limit(30, 60, scope="tutor_set_password"))])
async def set_password(body: SetPasswordRequest) -> dict:
    account = _account_or_404(body.account)
    try:
        done = tutor_account_store.set_password(account, body.password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not done:
        raise HTTPException(
            status_code=409,
            detail="Dieses Konto hat bereits ein Passwort. Bitte anmelden oder Passwort vergessen wählen.",
        )
    return {"status": "ok", "account": account}


@router.post("/reset-request", dependencies=[Depends(rate_limit(10, 60, scope="tutor_reset_request"))])
async def reset_request(body: ResetRequest) -> dict:
    account = _account_or_404(body.account)
    tutor_account_store.request_reset(account)
    return {"status": "requested", "account": account}


@router.post("/{account}/reset-code")
async def issue_reset_code(account: str, master: str | None = Depends(require_master_header)) -> dict:
    target = _account_or_404(account)
    issued = tutor_account_store.issue_reset_code(target, issued_by=master)
    if issued is None:
        raise HTTPException(status_code=404, detail="Unbekanntes Konto")
    code, expires_at = issued
    return {"account": target, "code": code, "expires_at": expires_at}


@router.get("/accounts")
async def list_accounts(master: str | None = Depends(require_master_header)) -> list[dict]:
    return [tutor_account_store.public_view(r) for r in tutor_account_store.list_all()]


__all__ = ["router", "TUTOR_ACCOUNTS"]
