"""ToAdapt — Transfer-Trainer für BWL A."""

import logging
from contextlib import asynccontextmanager

import os
from pathlib import Path

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
_log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        (
            structlog.processors.JSONRenderer()
            if ENVIRONMENT == "production"
            else structlog.dev.ConsoleRenderer()
        ),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(_log_level),
    cache_logger_on_first_use=True,
)

_sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
if _sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=ENVIRONMENT,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        # Keine Request-Bodies/PII an Sentry senden.
        send_default_pii=False,
    )

from backend.auth import require_api_key, student_access_required
from backend.api.routes import router as session_router
from backend.admin.routes import router as admin_router
from backend.dashboard.routes import router as dashboard_router
from backend.config.tp_configs import current_tp_phase
from backend.db.experiment_logger import experiment_logger
from backend.llm import DEFAULT_OPENROUTER_MODEL

logger = structlog.get_logger(__name__)
BUILD_MARKER = "railway-mongo-env-diagnostics-2026-05-14-1809z"


@asynccontextmanager
async def lifespan(app: FastAPI):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    mongo = experiment_logger.diagnostics
    # Kein Key-Material (auch keine Prefixe) und keine Env-Key-Namen loggen —
    # nur boolescher Konfigurationsstatus.
    logger.info(
        "toadapt_startup",
        tp_phase=current_tp_phase(),
        llm_provider="openrouter",
        llm_model=os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        openrouter_api_key_configured=bool(key),
        mongo_logging_enabled=mongo["enabled"],
        mongo_connection_mode=mongo["connection_mode"],
        student_access_code_configured=student_access_required(),
        sentry_enabled=bool(_sentry_dsn),
        environment=ENVIRONMENT,
    )
    if not student_access_required():
        logger.warning(
            "student_flow_open",
            hint="STUDENT_ACCESS_CODE ist nicht gesetzt — Sessions/Chat/Submissions sind öffentlich erreichbar.",
        )
    yield
    logger.info("toadapt_shutdown")


app = FastAPI(
    title="ToAdapt",
    description="Transfer-Trainer für BWL A",
    version="0.2.0",
    lifespan=lifespan,
)

def _allowed_origins() -> list[str]:
    """Erlaubte CORS-Origins aus ALLOWED_ORIGINS (kommagetrennt).

    Fällt in der Entwicklung auf localhost zurück. In Produktion MUSS
    ALLOWED_ORIGINS auf die konkrete Frontend-Domain gesetzt werden —
    ein Wildcard ist mit allow_credentials=True ohnehin unzulässig.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router)
app.include_router(admin_router)
app.include_router(dashboard_router)


from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health", tags=["meta"])
async def health() -> dict:
    # Bewusst minimal: keine Infrastruktur-Details (Mongo-Host/-Setup,
    # Env-Key-Namen, Feldlängen) auf einem öffentlichen Endpunkt.
    return {
        "status": "ok",
        "version": "0.2.0",
    }


@app.get("/health/diagnostics", tags=["meta"], dependencies=[Depends(require_api_key)])
async def health_diagnostics() -> dict:
    mongo = experiment_logger.diagnostics
    return {
        "status": "ok",
        "tp_phase": current_tp_phase(),
        "version": "0.2.0",
        "build_marker": BUILD_MARKER,
        "mongo_logging_enabled": mongo["enabled"],
        "mongo_connection_mode": mongo["connection_mode"],
        "mongo_database": mongo["database"],
        "mongo_collection": mongo["collection"],
        "mongo_has_uri": mongo["has_uri"],
        "mongo_env_keys": mongo["mongo_env_keys"],
        "mongodb_host_len": mongo["mongodb_host_len"],
        "mongodb_mas_name_len": mongo["mongodb_mas_name_len"],
        "mongodb_mas_key_len": mongo["mongodb_mas_key_len"],
        "mongodb_uri_len": mongo["mongodb_uri_len"],
        "mongo_last_connection_failure": mongo["last_connection_failure"],
    }
