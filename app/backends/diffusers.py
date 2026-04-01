from __future__ import annotations

import asyncio
import time

from PIL import Image

from app.backends.base import GenerationResult, InferenceBackend
from app.schemas import SessionConfig


class DiffusersBackend(InferenceBackend):
    name = "diffusers"

    def __init__(self) -> None:
        self.torch = None
        self.pipeline = None
        self.pipeline_model_id: str | None = None
        self.pipeline_mode: str | None = None
        self.scheduler_name: str | None = None

    async def setup(self) -> None:
        self.torch = self._import_torch()
        if not self.torch.cuda.is_available():
            raise RuntimeError("Diffusers backend requires a CUDA-capable GPU host")

    async def warmup(self, session_config: SessionConfig) -> None:
        await asyncio.to_thread(self._ensure_pipeline, session_config)

    async def generate(
        self,
        image: Image.Image,
        session_config: SessionConfig,
    ) -> GenerationResult:
        started = time.perf_counter()
        await asyncio.to_thread(self._ensure_pipeline, session_config)
        output = await asyncio.to_thread(self._run_generate, image, session_config)
        latency_ms = (time.perf_counter() - started) * 1000
        return GenerationResult(image=output, latency_ms=latency_ms)

    def _ensure_pipeline(self, config: SessionConfig) -> None:
        if self.torch is None:
            self.torch = self._import_torch()

        if (
            self.pipeline is None
            or self.pipeline_model_id != config.model_id_or_path
            or self.pipeline_mode != config.mode
        ):
            self.pipeline = self._build_pipeline(config)
            self.pipeline_model_id = config.model_id_or_path
            self.pipeline_mode = config.mode
            self.scheduler_name = None

        if self.scheduler_name != config.scheduler_name:
            self._apply_scheduler(config.scheduler_name)
            self.scheduler_name = config.scheduler_name

    def _build_pipeline(self, config: SessionConfig):
        pipeline_cls = self._resolve_pipeline_cls(config.mode)

        common_kwargs = {
            "torch_dtype": self._preferred_dtype(),
            "use_safetensors": True,
        }

        try:
            pipeline = pipeline_cls.from_pretrained(
                config.model_id_or_path,
                variant="fp16",
                **common_kwargs,
            )
        except Exception:
            pipeline = pipeline_cls.from_pretrained(
                config.model_id_or_path,
                **common_kwargs,
            )

        pipeline = pipeline.to("cuda")
        pipeline.set_progress_bar_config(disable=True)
        if hasattr(pipeline, "enable_attention_slicing"):
            pipeline.enable_attention_slicing()
        return pipeline

    def _run_generate(self, image: Image.Image, config: SessionConfig) -> Image.Image:
        generator = self.torch.Generator(device="cuda").manual_seed(config.seed)

        if config.mode == "txt2img":
            result = self.pipeline(
                prompt=config.prompt,
                negative_prompt=config.negative_prompt or None,
                width=config.width,
                height=config.height,
                guidance_scale=config.guidance_scale,
                num_inference_steps=config.denoise_steps,
                generator=generator,
            )
            return result.images[0].convert("RGB")

        prepared = image.convert("RGB").resize(
            (config.width, config.height),
            Image.Resampling.LANCZOS,
        )
        result = self.pipeline(
            prompt=config.prompt,
            negative_prompt=config.negative_prompt or None,
            image=prepared,
            strength=max(0.0, min(config.delta, 1.0)),
            guidance_scale=config.guidance_scale,
            num_inference_steps=config.denoise_steps,
            generator=generator,
        )
        return result.images[0].convert("RGB")

    @staticmethod
    def _import_torch():
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "Diffusers backend requires torch. Install the CUDA build of PyTorch on the Runpod host."
            ) from exc
        return torch

    @staticmethod
    def _resolve_pipeline_cls(mode: str):
        try:
            if mode == "txt2img":
                from diffusers import AutoPipelineForText2Image

                return AutoPipelineForText2Image

            from diffusers import AutoPipelineForImage2Image

            return AutoPipelineForImage2Image
        except ImportError as exc:
            raise RuntimeError(
                "Diffusers backend requires diffusers, transformers, accelerate, and safetensors."
            ) from exc

    def _apply_scheduler(self, scheduler_name: str) -> None:
        scheduler_map = self._scheduler_map()
        scheduler_cls = scheduler_map.get(scheduler_name.strip().lower())
        if scheduler_cls is None:
            return
        self.pipeline.scheduler = scheduler_cls.from_config(self.pipeline.scheduler.config)

    @staticmethod
    def _scheduler_map():
        try:
            from diffusers import DDIMScheduler, DPMSolverMultistepScheduler, EulerAncestralDiscreteScheduler, EulerDiscreteScheduler
        except ImportError as exc:
            raise RuntimeError(
                "Diffusers backend requires diffusers, transformers, accelerate, and safetensors."
            ) from exc

        return {
            "ddim": DDIMScheduler,
            "dpm": DPMSolverMultistepScheduler,
            "dpmsolvermultistep": DPMSolverMultistepScheduler,
            "euler": EulerDiscreteScheduler,
            "euler_a": EulerAncestralDiscreteScheduler,
            "eulera": EulerAncestralDiscreteScheduler,
        }

    def _preferred_dtype(self):
        if self.torch.cuda.is_bf16_supported():
            return self.torch.bfloat16
        return self.torch.float16
