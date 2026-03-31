from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    backend: str = "mock"
    streamdiffusion_root: str | None = None
    default_model: str = "stabilityai/sd-turbo"
    default_width: int = 512
    default_height: int = 512
    jpeg_quality: int = 88

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            host=os.getenv("LIVE_DIFFUSION_HOST", "0.0.0.0"),
            port=int(os.getenv("LIVE_DIFFUSION_PORT", "8000")),
            backend=os.getenv("LIVE_DIFFUSION_BACKEND", "mock").strip().lower(),
            streamdiffusion_root=os.getenv("STREAMDIFFUSION_TD_ROOT"),
            default_model=os.getenv("LIVE_DIFFUSION_MODEL", "stabilityai/sd-turbo"),
            default_width=int(os.getenv("LIVE_DIFFUSION_WIDTH", "512")),
            default_height=int(os.getenv("LIVE_DIFFUSION_HEIGHT", "512")),
            jpeg_quality=int(os.getenv("LIVE_DIFFUSION_JPEG_QUALITY", "88")),
        )

    def resolved_streamdiffusion_root(self) -> Path | None:
        if not self.streamdiffusion_root:
            return None
        return Path(self.streamdiffusion_root).expanduser().resolve()
