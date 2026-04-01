from __future__ import annotations

import asyncio
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
        self.package_root: Path | None = None
        self.stream_cls = None
        self.postprocess_image = None
        self.torch = None
        self.pipe = None
        self.stream = None
        self.active_config: SessionConfig | None = None

    async def setup(self) -> None:
        self.package_root = self._resolve_package_root()
        self._ensure_imports()

    async def warmup(self, session_config: SessionConfig) -> None:
        await asyncio.to_thread(self._ensure_stream, session_config)
        await asyncio.to_thread(self._warmup_stream, session_config)

    async def generate(
        self,
        image: Image.Image,
        session_config: SessionConfig,
    ) -> GenerationResult:
        started = time.perf_counter()
        await asyncio.to_thread(self._ensure_stream, session_config)
        output = await asyncio.to_thread(self._run_generate, image, session_config)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return GenerationResult(image=output, latency_ms=latency_ms)

    def _resolve_package_root(self) -> Path:
        candidates = [
            self.root,
            self.root / "src",
            self.root / "StreamDiffusion" / "src",
        ]
        for candidate in candidates:
            if (candidate / "streamdiffusion" / "__init__.py").exists():
                return candidate
        raise FileNotFoundError(
            "Could not locate plain StreamDiffusion package. "
            f"Checked: {', '.join(str(p) for p in candidates)}"
        )

    def _ensure_imports(self) -> None:
        if self.package_root is None:
            raise RuntimeError("StreamDiffusion package root is not resolved")
        package_root = str(self.package_root)
        if package_root not in sys.path:
            sys.path.insert(0, package_root)

        if self.stream_cls is None:
            import torch
            from diffusers import (
                AutoPipelineForImage2Image,
                AutoPipelineForText2Image,
            )
            from streamdiffusion import StreamDiffusion
            from streamdiffusion.image_utils import postprocess_image

            self.torch = torch
            self.AutoPipelineForImage2Image = AutoPipelineForImage2Image
            self.AutoPipelineForText2Image = AutoPipelineForText2Image
            self.stream_cls = StreamDiffusion
            self.postprocess_image = postprocess_image

    def _requires_rebuild(self, config: SessionConfig) -> bool:
        if self.active_config is None or self.pipe is None or self.stream is None:
            return True
        return any(
            (
                self.active_config.model_id_or_path != config.model_id_or_path,
                self.active_config.mode != config.mode,
                self.active_config.width != config.width,
                self.active_config.height != config.height,
                self.active_config.denoise_steps != config.denoise_steps,
                self.active_config.frame_buffer_size != config.frame_buffer_size,
                self.active_config.acceleration != config.acceleration,
                self.active_config.scheduler_name != config.scheduler_name,
                self.active_config.use_denoising_batch != config.use_denoising_batch,
            )
        )

    def _ensure_stream(self, config: SessionConfig) -> None:
        self._ensure_imports()

        if self._requires_rebuild(config):
            self.pipe = self._build_pipeline(config)
            self.stream = self._build_stream(self.pipe, config)
            self._prepare_stream(config)
            self.active_config = SessionConfig(**config.model_dump())
            return

        if any(
            (
                self.active_config.prompt != config.prompt,
                self.active_config.negative_prompt != config.negative_prompt,
                self.active_config.guidance_scale != config.guidance_scale,
                self.active_config.delta != config.delta,
                self.active_config.seed != config.seed,
            )
        ):
            self._prepare_stream(config)
            self.active_config = SessionConfig(**config.model_dump())

    def _build_pipeline(self, config: SessionConfig):
        torch = self.torch
        pipeline_cls = (
            self.AutoPipelineForImage2Image
            if config.mode == "img2img"
            else self.AutoPipelineForText2Image
        )
        pipe = pipeline_cls.from_pretrained(
            config.model_id_or_path,
            torch_dtype=torch.float16,
            variant="fp16",
        ).to(device=torch.device("cuda"))

        if config.acceleration == "xformers" and hasattr(pipe, "enable_xformers_memory_efficient_attention"):
            pipe.enable_xformers_memory_efficient_attention()

        return pipe

    def _build_stream(self, pipe, config: SessionConfig):
        cfg_type = "none" if config.guidance_scale <= 1e-6 else "self"
        stream = self.stream_cls(
            pipe,
            t_index_list=self._build_t_index_list(config.denoise_steps),
            torch_dtype=self.torch.float16,
            width=config.width,
            height=config.height,
            frame_buffer_size=config.frame_buffer_size,
            cfg_type=cfg_type,
            use_denoising_batch=config.use_denoising_batch,
        )
        return stream

    def _prepare_stream(self, config: SessionConfig) -> None:
        negative_prompt = config.negative_prompt or None
        self.stream.prepare(
            prompt=config.prompt,
            negative_prompt=negative_prompt,
            guidance_scale=config.guidance_scale,
            delta=config.delta,
            seed=config.seed,
        )

    def _warmup_stream(self, config: SessionConfig) -> None:
        warmup_count = max(1, config.denoise_steps * config.frame_buffer_size)
        dummy = Image.new("RGB", (config.width, config.height), color="black")
        for _ in range(warmup_count):
            if config.mode == "img2img":
                self._run_stream_img2img(dummy)
            else:
                self._run_stream_txt2img()

    def _run_generate(self, image: Image.Image, config: SessionConfig) -> Image.Image:
        if config.mode == "img2img":
            return self._run_stream_img2img(image)
        return self._run_stream_txt2img()

    def _run_stream_img2img(self, image: Image.Image) -> Image.Image:
        result = self.stream(image=image.convert("RGB"))
        return self._to_pil(result)

    def _run_stream_txt2img(self) -> Image.Image:
        if hasattr(self.stream, "txt2img"):
            result = self.stream.txt2img()
        else:
            result = self.stream()
        return self._to_pil(result)

    def _to_pil(self, result) -> Image.Image:
        if isinstance(result, Image.Image):
            return result.convert("RGB")
        processed = self.postprocess_image(result, output_type="pil")
        if isinstance(processed, list):
            processed = processed[0]
        return processed.convert("RGB")

    @staticmethod
    def _build_t_index_list(denoise_steps: int) -> list[int]:
        presets = {
            1: [32],
            2: [32, 45],
            3: [16, 32, 45],
            4: [0, 16, 32, 45],
        }
        if denoise_steps in presets:
            return presets[denoise_steps]
        if denoise_steps <= 1:
            return [32]
        max_t = 45
        if denoise_steps == 2:
            return [32, max_t]
        step = max_t / max(1, denoise_steps - 1)
        values = [int(round(i * step)) for i in range(denoise_steps)]
        return sorted(set(values))
