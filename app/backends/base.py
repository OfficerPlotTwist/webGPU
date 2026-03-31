from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from PIL import Image

from app.schemas import SessionConfig


@dataclass(slots=True)
class GenerationResult:
    image: Image.Image
    latency_ms: float


class InferenceBackend(ABC):
    name: str

    @abstractmethod
    async def setup(self) -> None:
        """Prepare shared backend resources."""

    @abstractmethod
    async def generate(
        self,
        image: Image.Image,
        session_config: SessionConfig,
    ) -> GenerationResult:
        """Generate one output frame."""
