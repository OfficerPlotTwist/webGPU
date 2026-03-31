# Remote Live Diffusion Relay

This project turns a rented GPU into a small appliance for live img2img diffusion driven by TouchDesigner or any other frame source.

It provides:

- a FastAPI service with HTTP and WebSocket endpoints
- a bounded session queue that drops stale frames under load
- a mock backend for local development
- an optional StreamDiffusion backend adapter for the real GPU host
- a simple Python bridge script you can mirror from TouchDesigner
- a rented-box smoke test script and show session template

## Why this exists

Your existing local `StreamDiffusionTD` setup assumes:

- local OSC for control
- shared memory for frame transfer
- the model process running on the same machine as TouchDesigner

This service keeps the same practical workflow, but replaces same-machine transport with a remote-safe API.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

## Endpoints

- `GET /health`
- `POST /sessions`
- `GET /sessions/{session_id}`
- `POST /sessions/{session_id}/config`
- `POST /sessions/{session_id}/frames`
- `WS /ws/{session_id}`

`POST /sessions/{session_id}/frames` accepts JSON:

- `image_base64`: encoded image bytes
- `image_format`: `jpeg` or `png`
- `settings`: optional per-frame overrides such as prompt or guidance scale

The WebSocket accepts JSON messages:

```json
{"image_base64":"...","image_format":"jpeg","settings":{"prompt":"blue smoke"}}
{"type":"session.update","config":{"prompt":"neon fog","width":512,"height":512}}
{"type":"frame.submit","frame_id":"123","image_base64":"...","image_format":"jpeg","settings":{"prompt":"blue smoke"}}
{"type":"ping"}
```

For lower-latency live streaming, prefer the hybrid protocol:

1. Send text:

```json
{"type":"frame.begin","frame_id":"123","image_format":"jpeg"}
```

2. Immediately send one binary WebSocket message containing the raw JPEG bytes.

3. The server replies with text metadata:

```json
{"type":"frame.result","frame_id":"123","image_format":"jpeg","latency_ms":84.2,"queue_depth":0}
```

4. The server then sends one binary WebSocket message containing the raw output JPEG bytes.

And returns:

```json
{"type":"session.ready","session_id":"...","backend":"mock"}
{"type":"frame.result","frame_id":"123","image_base64":"...","image_format":"jpeg","latency_ms":84.2}
{"type":"session.metrics","metrics":{"submitted":10,"processed":9,"dropped":1}}
{"type":"pong"}
```

## Backends

### Mock backend

Default for local development. It does not run diffusion. It returns a stylized version of the input frame so you can validate:

- transport
- queuing
- framing
- TouchDesigner integration

### StreamDiffusion backend

Set:

- `LIVE_DIFFUSION_BACKEND=streamdiffusion`
- `STREAMDIFFUSION_TD_ROOT=/workspace/StreamDiffusion/StreamDiffusion`

The adapter expects the remote machine to already have the StreamDiffusionTD dependencies installed. It loads `streamdiffusionTD/wrapper_td.py` dynamically and uses img2img mode.

## GPU host notes

Recommended show-day defaults:

- fixed `512x512` or `768x768`
- `sd-turbo` or similar low-step img2img model
- capped input FPS from TouchDesigner
- JPEG transport quality around `80-90`
- one session per show machine unless you have tested higher concurrency

## TouchDesigner integration

This repo includes `scripts/touchdesigner_bridge.py`, a small reference client that:

- opens a session
- pushes config
- sends frames over the preferred hybrid WebSocket protocol
- prints frame timing

Useful bring-up assets:

- `configs/show-main.session.json`: reusable SDXL Turbo session payload
- `scripts/smoke_test_remote.py`: verifies `/health`, session creation, and one binary WebSocket frame roundtrip

Example smoke test against a running server:

```powershell
python scripts/smoke_test_remote.py --base-url http://127.0.0.1:8000 --ws-url ws://127.0.0.1:8000/ws/show-main --save-output out\smoke.jpg
```

Example bridge run with a still image:

```powershell
python scripts/touchdesigner_bridge.py --base-url http://127.0.0.1:8000 --ws-url ws://127.0.0.1:8000/ws/show-main --session-id show-main --session-config configs/show-main.session.json --image path\to\frame.jpg --fps 4 --count 1 --save-dir out
```

For TouchDesigner proper, mirror the same message format from a `webSocket DAT` or a Python extension that captures frames from a TOP, compresses them, and submits only the newest frame when the previous one is still in flight.
