"""ToAdapt — Transfer-Trainer für BWL A, Universität St. Gallen."""

from contextlib import asynccontextmanager

import os
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routes import router as session_router
from backend.admin.routes import router as admin_router
from backend.dashboard.routes import router as dashboard_router
from backend.config.tp_configs import current_tp_phase
from backend.llm import DEFAULT_OPENROUTER_MODEL

logger = structlog.get_logger(__name__)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    all_keys = [k for k in os.environ.keys() if "OPENROUTER" in k.upper()]
    logger.info(
        "toadapt_startup",
        tp_phase=current_tp_phase(),
        llm_provider="openrouter",
        llm_model=os.environ.get("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        api_key_len=len(key),
        api_key_prefix=key[:12] if key else "MISSING",
        matching_env_keys=all_keys,
    )
    yield
    logger.info("toadapt_shutdown")


app = FastAPI(
    title="ToAdapt",
    description="Transfer-Trainer für BWL A — Universität St. Gallen",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "tp_phase": current_tp_phase(), "version": "0.2.0"}
