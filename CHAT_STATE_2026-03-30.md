# Chat State

Date: 2026-03-30

## Goal

Build a TouchDesigner-to-rented-GPU live diffusion pipeline for a show, optimized around `SDXL Turbo` on a rented `RTX 5090`.

## Current Implementation

This workspace now contains a remote relay service and TouchDesigner integration scaffolding.

### Relay service

- FastAPI server: [app/server.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/app/server.py)
- Session/queue handling: [app/session.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/app/session.py)
- Schemas: [app/schemas.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/app/schemas.py)

### Backends

- Mock backend for transport testing:
  [app/backends/mock.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/app/backends/mock.py)
- StreamDiffusion adapter backend:
  [app/backends/streamdiffusion.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/app/backends/streamdiffusion.py)

Important:
- There is **not yet** a native plain `diffusers` backend in this repo.
- Real inference currently expects a local `StreamDiffusion` checkout on the rented box.

### Transport protocol

The preferred protocol is now hybrid WebSocket:

1. Text message:
   `{"type":"frame.begin","frame_id":"...","image_format":"jpeg"}`
2. Binary WebSocket message:
   raw JPEG bytes
3. GPU returns text metadata:
   `frame.result`
4. GPU returns binary image bytes

HTTP JSON/base64 frame submit still exists as a fallback path.

## TouchDesigner Files

- Remote WebSocket DAT callbacks:
  [scripts/touchdesigner_remote_ws_callbacks.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/scripts/touchdesigner_remote_ws_callbacks.py)
- Script TOP decoder:
  [scripts/touchdesigner_script_top_decoder.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/scripts/touchdesigner_script_top_decoder.py)
- Reference bridge client:
  [scripts/touchdesigner_bridge.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/scripts/touchdesigner_bridge.py)

## Docs Added

- Main project README:
  [README.md](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/README.md)
- Rented box setup for RTX 5090 + SDXL Turbo:
  [docs/RTX5090_SDXL_TURBO_RENTED_BOX.md](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/docs/RTX5090_SDXL_TURBO_RENTED_BOX.md)

## Recommended Show Target

- GPU: rented `RTX 5090`
- Model: `stabilityai/sdxl-turbo`
- Mode: `img2img`
- Resolution: `512x512`
- Denoise steps: `1`
- Guidance scale: `0.0`
- Sender FPS cap: about `4-8`
- Output: `jpeg`

## Verified Locally

Verified in this workspace:

- API tests pass:
  `python -m pytest tests/test_api.py -q`
- Binary WebSocket roundtrip is covered by tests.

Not verified in this workspace:

- Real rented-GPU inference with the StreamDiffusion backend
- TouchDesigner runtime behavior on the actual machine

## Most Important Next Step

Best next engineering task:

- add a native `diffusers` SDXL Turbo backend to `app/backends/`

Why:
- removes the current dependency on a separate StreamDiffusion checkout
- simplifies rented-box setup
- lowers show-day integration risk

## Resume Notes

If resuming later, start by reading:

1. [docs/RTX5090_SDXL_TURBO_RENTED_BOX.md](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/docs/RTX5090_SDXL_TURBO_RENTED_BOX.md)
2. [app/server.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/app/server.py)
3. [scripts/touchdesigner_remote_ws_callbacks.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/scripts/touchdesigner_remote_ws_callbacks.py)
4. [scripts/touchdesigner_script_top_decoder.py](C:/Users/nik/Documents/AI/webGPU%20Live%20Diffusion/scripts/touchdesigner_script_top_decoder.py)
