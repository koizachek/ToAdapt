"""FastAPI Entrypoint für ToAdapt."""

import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config.tp_configs import current_tp_phase
from backend.models.message import Message
from backend.models.session import SessionCreate, SessionResponse
from backend.realtime.broadcast import (
    broadcast_agent_typing,
    broadcast_user_message,
)
from backend.realtime.presence import broadcast_presence
from backend.realtime.websocket import manager

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("toadapt_startup")
    yield
    logger.info("toadapt_shutdown")


app = FastAPI(
    title="ToAdapt",
    description="Multi-Agent Scaffolding System für BWL A — Universität St.Gallen",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "tp_phase": current_tp_phase()}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@app.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, tags=["sessions"])
async def create_session(body: SessionCreate) -> SessionResponse:
    """Erstellt eine neue Chat-Session für eine Gruppe.

    Gibt die Session-ID und die WebSocket-URL zurück.
    Platzhalter — wird in Phase 2 mit DB-Persistenz und Auth erweitert.
    """
    session_id = str(uuid.uuid4())
    tp_phase = current_tp_phase()

    logger.info("session_created", session_id=session_id, group_id=body.group_id, tp=tp_phase)

    return SessionResponse(
        session_id=session_id,
        group_id=body.group_id,
        tp_phase=tp_phase,
        websocket_url=f"/ws/{body.group_id}/{body.user_id}?session_id={session_id}",
    )


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/{group_id}/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    group_id: str,
    user_id: str,
    display_name: str = "Anonym",
) -> None:
    """WebSocket-Endpunkt für den Gruppen-Chat.

    Protokoll (JSON-Messages):
        Client → Server:
            { "type": "message", "content": "..." }

        Server → Client (broadcast):
            { "event": "user_message",   "user_id": ..., "display_name": ..., "content": ... }
            { "event": "agent_response", "agent_type": ..., "content": ... }
            { "event": "agent_typing",   "agent_type": ..., "is_typing": true/false }
            { "event": "presence_update", "online": [...], "count": N }
    """
    await manager.connect(websocket, group_id, user_id)

    # Presence-Update an alle senden (inkl. neuem Mitglied)
    # In Phase 2: display_names aus DB laden
    display_names = {user_id: display_name}
    await broadcast_presence(group_id, display_names)

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") != "message":
                continue

            content: str = data.get("content", "").strip()
            if not content:
                continue

            message_id = str(uuid.uuid4())

            # 1. Nachricht an andere Gruppenmitglieder broadcasten
            await broadcast_user_message(
                group_id=group_id,
                user_id=user_id,
                display_name=display_name,
                content=content,
                message_id=message_id,
            )

            # 2. Typing-Indikator senden
            await broadcast_agent_typing(group_id, agent_type="metacognitive", is_typing=True)

            # TODO (Phase 2): Orchestrator aufrufen
            # response = await orchestrator.route_message(group_id, session_id, content)
            # await broadcast_agent_response(group_id, response.agent_type, response.content, ...)

            await broadcast_agent_typing(group_id, agent_type="metacognitive", is_typing=False)

    except WebSocketDisconnect:
        manager.disconnect(group_id, user_id)
        await broadcast_presence(group_id, display_names)
        logger.info("ws_client_disconnected", group_id=group_id, user_id=user_id)
