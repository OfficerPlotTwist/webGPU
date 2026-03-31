#!/usr/bin/env bash
set -euo pipefail

cd /workspace/live-diffusion

cat > s.json <<'JSON'
{"session_id":"show-main","config":{"model_id_or_path":"stabilityai/sdxl-turbo","prompt":"neon fog","width":512,"height":512,"guidance_scale":0,"denoise_steps":1}}
JSON

curl -X POST 127.0.0.1:8000/sessions -H "Content-Type: application/json" -d @s.json
