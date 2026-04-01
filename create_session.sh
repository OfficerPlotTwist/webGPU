#!/usr/bin/env bash
set -euo pipefail

cd /workspace/live-diffusion

cat > s.json <<'JSON'
{"session_id":"show-main","config":{"model_id_or_path":"stabilityai/sdxl-turbo","prompt":"neon fog","width":256,"height":256,"guidance_scale":0,"delta":1.0,"denoise_steps":2,"frame_buffer_size":1,"use_denoising_batch":true,"acceleration":"none","scheduler_name":"Euler","mode":"img2img","output_format":"jpeg","jpeg_quality":88}}
JSON

curl -X POST 127.0.0.1:8000/sessions -H "Content-Type: application/json" -d @s.json
