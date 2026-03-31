#!/usr/bin/env bash
set -euo pipefail

cd /workspace/live-diffusion
source .venv/bin/activate

export LIVE_DIFFUSION_BACKEND=diffusers
export LIVE_DIFFUSION_MODEL=stabilityai/sdxl-turbo
export LIVE_DIFFUSION_WIDTH=512
export LIVE_DIFFUSION_HEIGHT=512
export LIVE_DIFFUSION_JPEG_QUALITY=88

uvicorn app.server:app --host 0.0.0.0 --port 8000
