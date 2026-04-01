from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from PIL import Image

from app.backends.base import InferenceBackend
from app.schemas import FrameResult, FrameSettings, SessionConfig, SessionMetrics, SessionSnapshot

logger = logging.getLogger("live_diffusion.session")


@dataclass(slots=True)
class FrameJob:
    frame_id: str
    image_bytes: bytes
    image_format: str
    future: asyncio.Future[FrameResult] | None = None
    websocket: WebSocket | None = None


class SessionState:
    def __init__(
        self,
        session_id: str,
        backend: InferenceBackend,
        config: SessionConfig,
    ) -> None:
        self.session_id = session_id
        self.backend = backend
        self.config = config
        self.metrics = SessionMetrics()
        self.connections: set[WebSocket] = set()
        self.pending_job: FrameJob | None = None
        self.pending_event = asyncio.Event()
        self.pending_lock = asyncio.Lock()
        self.worker_task: asyncio.Task[None] | None = None

    async def update_config(self, config: SessionConfig) -> None:
        self.config = config

    async def process_frame_now(
        self,
        image_bytes: bytes,
        image_format: str,
        settings: FrameSettings | None,
        frame_id: str | None = None,
    ) -> FrameResult:
        if settings is not None:
            self._apply_settings(settings)
        self.metrics.submitted += 1
        frame_id = frame_id or str(uuid.uuid4())
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        result = await self.backend.generate(image=image, session_config=self.config)
        payload = self._build_result(frame_id, result.image, result.latency_ms)
        self.metrics.processed += 1
        self.metrics.last_latency_ms = result.latency_ms
        return payload

    async def submit_frame(
        self,
        image_bytes: bytes,
        image_format: str,
        settings: FrameSettings | None,
        wait_for_result: bool,
        frame_id: str | None = None,
        websocket: WebSocket | None = None,
    ) -> FrameResult | None:
        if settings is not None:
            self._apply_settings(settings)

        frame_id = frame_id or str(uuid.uuid4())
        future: asyncio.Future[FrameResult] | None = None
        if wait_for_result:
            future = asyncio.get_running_loop().create_future()

        async with self.pending_lock:
            if self.pending_job is not None:
                logger.info(
                    "frame.drop session_id=%s dropped_frame_id=%s replacement_frame_id=%s",
                    self.session_id,
                    self.pending_job.frame_id,
                    frame_id,
                )
                self.metrics.dropped += 1
                if self.pending_job.future is not None and not self.pending_job.future.done():
                    self.pending_job.future.set_exception(RuntimeError("Dropped due to newer frame"))
            self.pending_job = FrameJob(
                frame_id=frame_id,
                image_bytes=image_bytes,
                image_format=image_format,
                future=future,
                websocket=websocket,
            )
            self.metrics.submitted += 1
            self.pending_event.set()
            self._ensure_worker()
            logger.info(
                "frame.enqueue session_id=%s frame_id=%s bytes=%s image_format=%s websocket_reply=%s",
                self.session_id,
                frame_id,
                len(image_bytes),
                image_format,
                websocket is not None,
            )

        if not wait_for_result:
            return None
        return await future

    async def add_connection(self, websocket: WebSocket) -> None:
        self.connections.add(websocket)

    async def remove_connection(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    def snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(
            session_id=self.session_id,
            backend=self.backend.name,
            config=self.config,
            metrics=self.metrics,
        )

    def _apply_settings(self, settings: FrameSettings) -> None:
        update = self.config.model_dump()
        for key, value in settings.model_dump(exclude_none=True).items():
            update[key] = value
        self.config = SessionConfig(**update)

    def _ensure_worker(self) -> None:
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        while True:
            await self.pending_event.wait()
            async with self.pending_lock:
                job = self.pending_job
                self.pending_job = None
                if self.pending_job is None:
                    self.pending_event.clear()
            if job is None:
                continue

            try:
                logger.info(
                    "frame.process_start session_id=%s frame_id=%s bytes=%s",
                    self.session_id,
                    job.frame_id,
                    len(job.image_bytes),
                )
                image = Image.open(io.BytesIO(job.image_bytes)).convert("RGB")
                result = await self.backend.generate(image=image, session_config=self.config)
                payload = self._build_result(job.frame_id, result.image, result.latency_ms)
                self.metrics.processed += 1
                self.metrics.last_latency_ms = result.latency_ms
                logger.info(
                    "frame.process_done session_id=%s frame_id=%s latency_ms=%.1f output_format=%s",
                    self.session_id,
                    job.frame_id,
                    result.latency_ms,
                    payload.image_format,
                )
                if job.future is not None and not job.future.done():
                    job.future.set_result(payload)
                if job.websocket is not None:
                    logger.info(
                        "frame.reply_ws session_id=%s frame_id=%s binary_bytes=%s",
                        self.session_id,
                        payload.frame_id,
                        len(base64.b64decode(payload.image_base64)),
                    )
                    await job.websocket.send_json(
                        {
                            "type": "frame.result",
                            "frame_id": payload.frame_id,
                            "image_format": payload.image_format,
                            "latency_ms": payload.latency_ms,
                            "queue_depth": payload.queue_depth,
                        }
                    )
                    await job.websocket.send_bytes(base64.b64decode(payload.image_base64))
                else:
                    await self._broadcast(
                        {
                            "type": "frame.result",
                            **payload.model_dump(),
                        }
                    )
                await self._broadcast(
                    {
                        "type": "session.metrics",
                        "metrics": self.metrics.model_dump(),
                    }
                )
            except Exception as exc:
                logger.exception(
                    "frame.process_error session_id=%s frame_id=%s error=%s",
                    self.session_id,
                    job.frame_id,
                    exc,
                )
                self.metrics.failed += 1
                if job.future is not None and not job.future.done():
                    job.future.set_exception(exc)
                await self._broadcast(
                    {
                        "type": "frame.error",
                        "frame_id": job.frame_id,
                        "error": str(exc),
                    }
                )

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        if not self.connections:
            return
        message = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in self.connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.discard(ws)

    def _build_result(self, frame_id: str, image: Image.Image, latency_ms: float) -> FrameResult:
        encoded = self._encode_image(image, self.config.output_format, self.config.jpeg_quality)
        return FrameResult(
            frame_id=frame_id,
            image_base64=base64.b64encode(encoded).decode("ascii"),
            image_format=self.config.output_format,
            latency_ms=latency_ms,
            queue_depth=1 if self.pending_job is not None else 0,
        )

    @staticmethod
    def _encode_image(image: Image.Image, image_format: str, jpeg_quality: int) -> bytes:
        buffer = io.BytesIO()
        save_format = "JPEG" if image_format == "jpeg" else "PNG"
        params: dict[str, Any] = {}
        if save_format == "JPEG":
            params["quality"] = jpeg_quality
        image.save(buffer, format=save_format, **params)
        return buffer.getvalue()


class SessionRegistry:
    def __init__(self, backend: InferenceBackend, default_config: SessionConfig) -> None:
        self.backend = backend
        self.default_config = default_config
        self.sessions: dict[str, SessionState] = {}

    async def get_or_create(self, session_id: str | None, config: SessionConfig | None = None) -> SessionState:
        session_id = session_id or str(uuid.uuid4())
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(
                session_id=session_id,
                backend=self.backend,
                config=config or SessionConfig(**self.default_config.model_dump()),
            )
        elif config is not None:
            await self.sessions[session_id].update_config(config)
        return self.sessions[session_id]

    def get(self, session_id: str) -> SessionState:
        return self.sessions[session_id]
