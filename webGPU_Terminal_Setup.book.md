# webGPU Terminal Setup

This file collects the terminal commands discussed for bringing up this repo on a Runpod-style NVIDIA GPU host.

Important note:

- For `SDXL` on `Runpod`, the practical inference path is `CUDA + PyTorch`, not browser-style `WebGPU`.
- `WebGPU` is mainly relevant on the client side. The remote GPU box should run the model with CUDA.

## Basic Git Commands

```bash
git status
git add app/backends/diffusers.py app/server.py README.md docs/RTX5090_SDXL_TURBO_RENTED_BOX.md
git commit -m "Add diffusers backend for Runpod SDXL"
git status
git branch --show-current
git push origin <your-branch-name>
```

## Create And Activate Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Install PyTorch With CUDA

Run this on one line:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

## Install Diffusers Stack

```bash
pip install diffusers transformers accelerate safetensors huggingface_hub
```

## Full Runpod Setup Sequence

```bash
cd /workspace/live-diffusion
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install diffusers transformers accelerate safetensors huggingface_hub
export LIVE_DIFFUSION_BACKEND=diffusers
export LIVE_DIFFUSION_MODEL=stabilityai/sdxl-turbo
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

## Optional Hugging Face Login

```bash
huggingface-cli login
```

## Optional Pre-Download Of Model Weights

```bash
python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download("stabilityai/sdxl-turbo")
snapshot_download("madebyollin/taesdxl")
PY
```

## Health Check

```bash
curl http://127.0.0.1:8000/health
```

## Expected Runtime Environment

```bash
export LIVE_DIFFUSION_BACKEND=diffusers
export LIVE_DIFFUSION_MODEL=stabilityai/sdxl-turbo
export LIVE_DIFFUSION_WIDTH=512
export LIVE_DIFFUSION_HEIGHT=512
export LIVE_DIFFUSION_JPEG_QUALITY=88
```
