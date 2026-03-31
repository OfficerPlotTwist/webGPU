from __future__ import annotations

import asyncio
import time

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.backends.base import GenerationResult, InferenceBackend
from app.schemas import SessionConfig


class MockInferenceBackend(InferenceBackend):
    name = "mock"

    async def setup(self) -> None:
        return None

    async def generate(
        self,
        image: Image.Image,
        session_config: SessionConfig,
    ) -> GenerationResult:
        started = time.perf_counter()
        await asyncio.sleep(0.03)

        base = image.convert("RGB").resize(
            (session_config.width, session_config.height),
            Image.Resampling.LANCZOS,
        )
        stylized = ImageOps.autocontrast(base)
        stylized = stylized.filter(ImageFilter.DETAIL)
        stylized = ImageEnhance.Color(stylized).enhance(1.45)
        stylized = ImageEnhance.Contrast(stylized).enhance(1.2)
        edges = ImageOps.posterize(stylized, bits=5)

        latency_ms = (time.perf_counter() - started) * 1000
        return GenerationResult(image=edges, latency_ms=latency_ms)
