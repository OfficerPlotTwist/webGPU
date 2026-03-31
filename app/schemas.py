from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = ""
    negative_prompt: str = ""
    model_id_or_path: str = "stabilityai/sd-turbo"
    width: int = Field(default=512, ge=64, le=2048)
    height: int = Field(default=512, ge=64, le=2048)
    guidance_scale: float = Field(default=1.0, ge=0.0, le=20.0)
    delta: float = Field(default=1.0, ge=0.0, le=5.0)
    denoise_steps: int = Field(default=1, ge=1, le=8)
    seed: int = 2416333
    scheduler_name: str = "Euler"
    frame_buffer_size: int = Field(default=1, ge=1, le=4)
    use_denoising_batch: bool = True
    acceleration: Literal["none", "xformers", "tensorrt"] = "none"
    mode: Literal["img2img", "txt2img"] = "img2img"
    output_format: Literal["jpeg", "png"] = "jpeg"
    jpeg_quality: int = Field(default=88, ge=40, le=100)


class SessionCreateRequest(BaseModel):
    session_id: str | None = None
    config: SessionConfig | None = None


class SessionCreateResponse(BaseModel):
    session_id: str
    backend: str
    config: SessionConfig


class SessionConfigUpdate(BaseModel):
    config: SessionConfig


class FrameSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str | None = None
    negative_prompt: str | None = None
    guidance_scale: float | None = None
    delta: float | None = None
    seed: int | None = None


class FrameResult(BaseModel):
    frame_id: str
    image_base64: str
    image_format: Literal["jpeg", "png"]
    latency_ms: float
    queue_depth: int


class HTTPFrameRequest(BaseModel):
    image_base64: str
    image_format: Literal["jpeg", "png"] = "jpeg"
    settings: FrameSettings | None = None


class SessionMetrics(BaseModel):
    submitted: int = 0
    processed: int = 0
    dropped: int = 0
    failed: int = 0
    last_latency_ms: float | None = None


class SessionSnapshot(BaseModel):
    session_id: str
    backend: str
    config: SessionConfig
    metrics: SessionMetrics


class WSMessage(BaseModel):
    type: str
    frame_id: str | None = None
    config: SessionConfig | None = None
    settings: FrameSettings | None = None
    image_base64: str | None = None
    image_format: Literal["jpeg", "png"] | None = None
    data: dict[str, Any] | None = None
