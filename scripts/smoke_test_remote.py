from __future__ import annotations

import argparse
import io
import json
import time
import urllib.request
import uuid
from pathlib import Path

from PIL import Image


def http_json(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def load_session_payload(config_path: Path, session_id: str) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "config" not in payload:
        raise ValueError("Session payload must include a top-level 'config' object")
    payload["session_id"] = session_id
    return payload


def build_probe_frame(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color=(20, 30, 40))
    for x in range(0, width, max(1, width // 8)):
        for y in range(height):
            image.putpixel((x, y), (255, 120, 40))
    for y in range(0, height, max(1, height // 8)):
        for x in range(width):
            image.putpixel((x, y), (40, 200, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88)
    return buffer.getvalue()


async def websocket_probe(ws_url: str, image_bytes: bytes, output_path: Path | None) -> dict:
    from websockets.asyncio.client import connect

    frame_id = str(uuid.uuid4())
    started = time.perf_counter()

    async with connect(ws_url, max_size=32_000_000) as websocket:
        ready_raw = await websocket.recv()
        ready = json.loads(ready_raw)
        await websocket.send(
            json.dumps(
                {
                    "type": "frame.begin",
                    "frame_id": frame_id,
                    "image_format": "jpeg",
                }
            )
        )
        await websocket.send(image_bytes)

        result = None
        output_bytes = None
        while result is None or output_bytes is None:
            raw = await websocket.recv()
            if isinstance(raw, bytes):
                output_bytes = raw
            else:
                message = json.loads(raw)
                if message.get("type") == "frame.result" and message.get("frame_id") == frame_id:
                    result = message

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if output_path is not None and output_bytes is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(output_bytes)

    return {
        "ready": ready,
        "result": result,
        "output_bytes": len(output_bytes or b""),
        "elapsed_ms": elapsed_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a rented live diffusion relay over HTTP and hybrid WebSocket.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/ws/show-main")
    parser.add_argument("--session-config", default="configs/show-main.session.json")
    parser.add_argument("--session-id", default="show-main")
    parser.add_argument("--save-output")
    args = parser.parse_args()

    session_payload = load_session_payload(Path(args.session_config), args.session_id)

    health = http_json("GET", f"{args.base_url}/health")
    print(f"health={json.dumps(health)}")

    created = http_json("POST", f"{args.base_url}/sessions", session_payload)
    print(f"session_created={created['session_id']} backend={created['backend']}")

    config = session_payload["config"]
    probe = build_probe_frame(int(config["width"]), int(config["height"]))

    import asyncio

    result = asyncio.run(
        websocket_probe(
            ws_url=args.ws_url,
            image_bytes=probe,
            output_path=Path(args.save_output) if args.save_output else None,
        )
    )

    print(f"session_ready={json.dumps(result['ready'])}")
    print(f"frame_result={json.dumps(result['result'])}")
    print(f"output_bytes={result['output_bytes']}")
    print(f"roundtrip_elapsed_ms={result['elapsed_ms']:.1f}")


if __name__ == "__main__":
    main()
