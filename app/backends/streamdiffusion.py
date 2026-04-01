from __future__ import annotations

import asyncio
import importlib.util
import sys
import time
from pathlib import Path

from PIL import Image

from app.backends.base import GenerationResult, InferenceBackend
from app.schemas import SessionConfig


class StreamDiffusionBackend(InferenceBackend):
    name = "streamdiffusion"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.wrapper_module = None
        self.wrapper = None
        self.active_config: SessionConfig | None = None

    async def setup(self) -> None:
        if not self.root.exists():
            raise FileNotFoundError(f"STREAMDIFFUSION_TD_ROOT does not exist: {self.root}")

    async def warmup(self, session_config: SessionConfig) -> None:
        await asyncio.to_thread(self._ensure_wrapper, session_config)

    async def generate(
        self,
        image: Image.Image,
        session_config: SessionConfig,
    ) -> GenerationResult:
        started = time.perf_counter()
        await asyncio.to_thread(self._ensure_wrapper, session_config)
        output = await asyncio.to_thread(self._run_generate, image, session_config)
        latency_ms = (time.perf_counter() - started) * 1000
        return GenerationResult(image=output, latency_ms=latency_ms)

    def _ensure_wrapper(self, config: SessionConfig) -> None:
        if self.wrapper_module is None:
            self.wrapper_module = self._load_wrapper_module()

        if self.wrapper is None or self.active_config != config:
            wrapper_cls = getattr(self.wrapper_module, "StreamDiffusionWrapper")
            self.wrapper = wrapper_cls(
                model_id_or_path=config.model_id_or_path,
                t_index_list=[9] * config.denoise_steps,
                mode=config.mode,
                output_type="pil",
                width=config.width,
                height=config.height,
                frame_buffer_size=config.frame_buffer_size,
                acceleration=config.acceleration,
                use_denoising_batch=config.use_denoising_batch,
                scheduler_name=config.scheduler_name,
            )
            self.wrapper.prepare(
                prompt=config.prompt,
                negative_prompt=config.negative_prompt,
                guidance_scale=config.guidance_scale,
                delta=config.delta,
                seed=config.seed,
            )
            self.active_config = config
        elif self.active_config.prompt != config.prompt or self.active_config.negative_prompt != config.negative_prompt:
            self.wrapper.prepare(
                prompt=config.prompt,
                negative_prompt=config.negative_prompt,
                guidance_scale=config.guidance_scale,
                delta=config.delta,
                seed=config.seed,
            )
            self.active_config = config

    def _run_generate(self, image: Image.Image, config: SessionConfig) -> Image.Image:
        result = self.wrapper(image=image)
        if isinstance(result, list):
            result = result[0]
        return result.convert("RGB")

    def _load_wrapper_module(self):
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        td_root = self.root / "streamdiffusionTD"
        if str(td_root) not in sys.path:
            sys.path.insert(0, str(td_root))

        wrapper_path = td_root / "wrapper_td.py"
        spec = importlib.util.spec_from_file_location("remote_streamdiffusion_wrapper", wrapper_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load StreamDiffusion wrapper from {wrapper_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
