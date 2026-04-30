"""ToAdapt — Transfer-Trainer für BWL A, Universität St. Gallen."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as session_router
from backend.admin.routes import router as admin_router
from backend.dashboard.routes import router as dashboard_router
from backend.config.tp_configs import current_tp_phase

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("toadapt_startup", tp_phase=current_tp_phase())
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


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "tp_phase": current_tp_phase(), "version": "0.2.0"}
