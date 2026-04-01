#!/usr/bin/env bash
set -euo pipefail

cd /workspace/live-diffusion
source .venv/bin/activate

export LIVE_DIFFUSION_MODEL=stabilityai/sdxl-turbo
export LIVE_DIFFUSION_WIDTH=256
export LIVE_DIFFUSION_HEIGHT=256
export LIVE_DIFFUSION_JPEG_QUALITY=88

export LIVE_DIFFUSION_BACKEND=streamdiffusion
export STREAMDIFFUSION_TD_ROOT="${STREAMDIFFUSION_TD_ROOT:-/workspace/StreamDiffusion/StreamDiffusion}"

if [[ ! -d "${STREAMDIFFUSION_TD_ROOT}" ]]; then
    echo "STREAMDIFFUSION_TD_ROOT not found: ${STREAMDIFFUSION_TD_ROOT}" >&2
    echo "Set STREAMDIFFUSION_TD_ROOT to your StreamDiffusionTD checkout before starting the server." >&2
    exit 1
fi

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
