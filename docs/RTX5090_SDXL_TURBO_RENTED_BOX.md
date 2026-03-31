# RTX 5090 + SDXL Turbo Rented Box Setup

This is the exact setup I would use for a short live show on a rented `RTX 5090` box.

Date context: this doc was written on `2026-03-30`.

## Goal

Bring up a rented Linux GPU machine that:

- runs the relay service in this repo
- pre-downloads `SDXL Turbo` weights before the show
- is ready for TouchDesigner to connect over WebSocket

## Important constraint in the current repo

The relay service in this repo has:

- a `mock` backend for transport testing
- a `streamdiffusion` backend adapter for real inference

The current repo does **not** yet include a plain `diffusers` backend. That means real inference currently expects a local `StreamDiffusion` checkout on the rented box.

If you want to avoid that dependency, the next code change should be adding a native `diffusers` backend to `app/backends/`.

## Assumptions

- OS: Ubuntu `22.04` or `24.04`
- GPU: `RTX 5090`
- NVIDIA driver already works on the host
- Python: `3.11`
- You have a Hugging Face token and have accepted the model license if required
- You are running one live stream, not multiple concurrent sessions

## 1. Create the box

Use a rented box with:

- `RTX 5090`
- at least `32 GB` VRAM
- at least `100 GB` disk
- good upload/download bandwidth
- public TCP access on port `8000`

Recommended server region:

- as close as possible to the venue/operator machine

## 2. Check the GPU first

SSH into the box and verify the GPU is visible:

```bash
nvidia-smi
```

You want to see:

- the `RTX 5090`
- recent driver loaded correctly
- no existing memory pressure from other processes

## 3. Install system packages

```bash
sudo apt-get update
sudo apt-get install -y git python3.11 python3.11-venv python3-pip
```

If `python3.11` is already the default, that is fine.

## 4. Clone the relay repo

```bash
git clone <YOUR-REPO-URL> live-diffusion
cd live-diffusion
```

## 5. Create the relay virtualenv

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 6. Install PyTorch for the GPU

Use the current official PyTorch install command for Linux + CUDA from the PyTorch selector.

At the time of writing, the official selector is here:

- https://pytorch.org/get-started/locally/

Example pattern:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Do not guess an older CUDA wheel for a `5090` unless you have already tested it on that host.

## 7. Install the real inference stack dependencies

The current real backend in this repo expects a `StreamDiffusion` checkout.

Clone it beside this repo:

```bash
cd ..
git clone https://github.com/cumulo-autumn/StreamDiffusion.git
cd StreamDiffusion
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install PyTorch in this env too:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

Install the TD requirements that exist in your local workflow:

```bash
pip install -r StreamDiffusionTD/requirements_pc.txt
```

Notes:

- `pywin32` is listed in that requirements file but is Windows-only. If install fails on Linux because of `pywin32`, remove that single package from the install list and continue.
- If `xformers` is needed later, install it only after the base environment is working.

## 8. Log into Hugging Face

Activate whichever env you want to use for downloading. The StreamDiffusion env is the safer choice because that is where real inference will run.

```bash
source .venv/bin/activate
huggingface-cli login
```

Paste your token when prompted.

## 9. Pre-download SDXL Turbo weights before the show

This avoids first-frame stalls.

The official SDXL Turbo docs:

- https://huggingface.co/docs/diffusers/main/en/using-diffusers/sdxl_turbo

The model:

- https://huggingface.co/stabilityai/sdxl-turbo

Pre-download the main model and Tiny VAE:

```bash
python - <<'PY'
from huggingface_hub import snapshot_download

snapshot_download("stabilityai/sdxl-turbo")
snapshot_download("madebyollin/taesdxl")
PY
```

If you want the weights in a known location, set:

```bash
export HF_HOME=/workspace/hf-cache
```

before running the download.

## 10. Return to the relay repo

```bash
cd ../live-diffusion
source .venv/bin/activate
```

## 11. Set the runtime environment

Set these env vars before launching the relay:

```bash
export LIVE_DIFFUSION_BACKEND=streamdiffusion
export STREAMDIFFUSION_TD_ROOT=$(realpath ../StreamDiffusion/StreamDiffusion)
export LIVE_DIFFUSION_MODEL=stabilityai/sdxl-turbo
export LIVE_DIFFUSION_WIDTH=512
export LIVE_DIFFUSION_HEIGHT=512
export LIVE_DIFFUSION_JPEG_QUALITY=88
```

Recommended show defaults:

- `512x512`
- `1` denoise step
- JPEG output
- no multi-session concurrency

## 12. Start the relay

```bash
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

If you want it to survive disconnects:

```bash
tmux new -s diffusion
source .venv/bin/activate
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

Detach with `Ctrl+B` then `D`.

## 13. Verify health

On the rented box:

```bash
curl http://127.0.0.1:8000/health
```

Expected result:

```json
{"status":"ok","backend":"streamdiffusion"}
```

## 14. Create the session

Use the checked-in template:

```bash
cat configs/show-main.session.json
```

Then post it:

```bash
curl -X POST http://127.0.0.1:8000/sessions \
  -H "Content-Type: application/json" \
  -d @configs/show-main.session.json
```

## 15. Run the rented-box smoke test

Before TouchDesigner, verify the relay and backend path directly:

```bash
python scripts/smoke_test_remote.py \
  --base-url http://127.0.0.1:8000 \
  --ws-url ws://127.0.0.1:8000/ws/show-main \
  --save-output out/smoke.jpg
```

This checks:

- `/health`
- session creation
- one hybrid WebSocket frame roundtrip
- returned binary output bytes

## 16. Connect TouchDesigner

Point the `webSocket DAT` at:

```text
ws://<YOUR-GPU-IP>:8000/ws/show-main
```

Use the TouchDesigner scripts in this repo:

- [touchdesigner_remote_ws_callbacks.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/scripts/touchdesigner_remote_ws_callbacks.py)
- [touchdesigner_script_top_decoder.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/scripts/touchdesigner_script_top_decoder.py)

Optional non-TouchDesigner bridge check:

```bash
python scripts/touchdesigner_bridge.py \
  --base-url http://127.0.0.1:8000 \
  --ws-url ws://127.0.0.1:8000/ws/show-main \
  --session-id show-main \
  --session-config configs/show-main.session.json \
  --image path/to/frame.jpg \
  --fps 4 \
  --count 1 \
  --save-dir out
```

## 17. Show-day checklist

Before doors open:

1. Run `nvidia-smi`
2. Confirm `/health`
3. Run `python scripts/smoke_test_remote.py`
4. Confirm session creation works
5. Send one test frame from TouchDesigner
6. Confirm output appears in the Script TOP
7. Keep the resolution at `512x512` unless you have already tested `768x768`

## 18. Known risk

The transport path in this repo is tested locally, but the `streamdiffusion` backend path was not validated on a real rented `RTX 5090` inside this workspace. The most likely friction point is Python package compatibility in the upstream `StreamDiffusion` environment, not the relay itself.

## Sources

- PyTorch install selector: https://pytorch.org/get-started/locally/
- SDXL Turbo docs: https://huggingface.co/docs/diffusers/main/en/using-diffusers/sdxl_turbo
- SDXL Turbo model card: https://huggingface.co/stabilityai/sdxl-turbo
- StreamDiffusion repo: https://github.com/cumulo-autumn/StreamDiffusion
