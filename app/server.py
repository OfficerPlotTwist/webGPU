from __future__ import annotations

import base64
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from app.backends.diffusers import DiffusersBackend
from app.backends.mock import MockInferenceBackend
from app.backends.streamdiffusion import StreamDiffusionBackend
from app.config import AppConfig
from app.schemas import HTTPFrameRequest, SessionConfig, SessionCreateRequest, SessionCreateResponse, SessionConfigUpdate, WSMessage
from app.session import SessionRegistry

config = AppConfig.from_env()
logger = logging.getLogger("live_diffusion.ws")


def create_backend():
    if config.backend == "mock":
        return MockInferenceBackend()
    if config.backend == "diffusers":
        return DiffusersBackend()
    if config.backend == "streamdiffusion":
        root = config.resolved_streamdiffusion_root()
        if root is None:
            raise RuntimeError("STREAMDIFFUSION_TD_ROOT is required when LIVE_DIFFUSION_BACKEND=streamdiffusion")
        return StreamDiffusionBackend(root)
    raise RuntimeError(f"Unsupported backend: {config.backend}")


backend = create_backend()
registry = SessionRegistry(
    backend=backend,
    default_config=SessionConfig(
        model_id_or_path=config.default_model,
        width=config.default_width,
        height=config.default_height,
        jpeg_quality=config.jpeg_quality,
    ),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await backend.setup()
    yield


app = FastAPI(title="Remote Live Diffusion Relay", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "backend": backend.name}


@app.post("/warmup")
async def warmup() -> dict[str, str]:
    await backend.warmup(registry.default_config)
    return {
        "status": "ok",
        "backend": backend.name,
        "model_id_or_path": registry.default_config.model_id_or_path,
        "mode": registry.default_config.mode,
    }


@app.post("/sessions", response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest) -> SessionCreateResponse:
    session = await registry.get_or_create(request.session_id, request.config)
    return SessionCreateResponse(
        session_id=session.session_id,
        backend=backend.name,
        config=session.config,
    )


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        return registry.get(session_id).snapshot()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc


@app.post("/sessions/{session_id}/config")
async def update_session_config(session_id: str, request: SessionConfigUpdate):
    try:
        session = registry.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    await session.update_config(request.config)
    return session.snapshot()


@app.post("/sessions/{session_id}/frames")
async def submit_frame(
    session_id: str,
    request: HTTPFrameRequest,
):
    try:
        session = registry.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc

    result = await session.process_frame_now(
        image_bytes=base64.b64decode(request.image_base64),
        image_format=request.image_format,
        settings=request.settings,
    )
    return result


@app.websocket("/ws/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    client = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    logger.info("ws.accept session_id=%s client=%s", session_id, client)
    session = await registry.get_or_create(session_id)
    await session.add_connection(websocket)
    pending_binary_meta: dict[str, str] | None = None
    await websocket.send_json(
        {
            "type": "session.ready",
            "session_id": session_id,
            "backend": backend.name,
            "config": session.config.model_dump(),
        }
    )
    try:
        while True:
            message_in = await websocket.receive()
            if "text" in message_in and message_in["text"] is not None:
                raw = message_in["text"]
                message = WSMessage.model_validate_json(raw)
                logger.info(
                    "ws.text session_id=%s client=%s type=%s frame_id=%s has_config=%s has_image_base64=%s",
                    session_id,
                    client,
                    message.type,
                    message.frame_id,
                    message.config is not None,
                    bool(message.image_base64),
                )

                if message.type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                if message.type == "session.update":
                    if message.config is None:
                        raise ValueError("session.update requires config")
                    await session.update_config(message.config)
                    await websocket.send_json(
                        {"type": "session.updated", "config": session.config.model_dump()}
                    )
                    continue

                if message.type == "frame.submit":
                    if not message.image_base64 or not message.image_format:
                        raise ValueError("frame.submit requires image_base64 and image_format")
                    await session.submit_frame(
                        image_bytes=base64.b64decode(message.image_base64),
                        image_format=message.image_format,
                        settings=message.settings,
                        wait_for_result=False,
                        frame_id=message.frame_id,
                        websocket=websocket,
                    )
                    continue

                if message.type == "frame.begin":
                    if not message.frame_id or not message.image_format:
                        raise ValueError("frame.begin requires frame_id and image_format")
                    pending_binary_meta = {
                        "frame_id": message.frame_id,
                        "image_format": message.image_format,
                    }
                    logger.info(
                        "ws.frame_begin session_id=%s client=%s frame_id=%s image_format=%s",
                        session_id,
                        client,
                        message.frame_id,
                        message.image_format,
                    )
                    continue

                await websocket.send_json({"type": "warning", "message": f"Unknown message type: {message.type}"})
                continue

            if "bytes" in message_in and message_in["bytes"] is not None:
                if pending_binary_meta is None:
                    raise ValueError("Received binary frame without preceding frame.begin")
                logger.info(
                    "ws.binary session_id=%s client=%s frame_id=%s bytes=%s",
                    session_id,
                    client,
                    pending_binary_meta["frame_id"],
                    len(message_in["bytes"]),
                )
                await session.submit_frame(
                    image_bytes=message_in["bytes"],
                    image_format=pending_binary_meta["image_format"],
                    settings=None,
                    wait_for_result=False,
                    frame_id=pending_binary_meta["frame_id"],
                    websocket=websocket,
                )
                pending_binary_meta = None
                continue

            if message_in.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()
    except WebSocketDisconnect:
        logger.info("ws.disconnect session_id=%s client=%s", session_id, client)
        await session.remove_connection(websocket)
    except Exception as exc:
        logger.exception("ws.error session_id=%s client=%s error=%s", session_id, client, exc)
        await websocket.send_json({"type": "session.error", "error": str(exc)})
        await session.remove_connection(websocket)
