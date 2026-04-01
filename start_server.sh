#!/usr/bin/env bash
set -euo pipefail

cd /workspace/live-diffusion
source .venv/bin/activate

export LIVE_DIFFUSION_BACKEND=diffusers
export LIVE_DIFFUSION_MODEL=stabilityai/sdxl-turbo
export LIVE_DIFFUSION_WIDTH=512
export LIVE_DIFFUSION_HEIGHT=512
export LIVE_DIFFUSION_JPEG_QUALITY=88

cleanup() {
    if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
        kill "${SERVER_PID}" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

uvicorn app.server:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

until curl -sf http://127.0.0.1:8000/health >/dev/null; do
    if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
        wait "${SERVER_PID}"
    fi
    sleep 1
done

echo "Server health is ok. Preloading pipeline..."
curl -sf -X POST http://127.0.0.1:8000/warmup >/dev/null
echo "Pipeline warmup complete."

wait "${SERVER_PID}"
