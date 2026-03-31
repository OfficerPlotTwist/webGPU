from __future__ import annotations

import argparse
import asyncio
import io
import json
import time
import urllib.request
import uuid
from pathlib import Path

from PIL import Image


def create_session(base_url: str, session_id: str, config: dict) -> None:
    payload = json.dumps(
        {
            "session_id": session_id,
            "config": config,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/sessions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        response.read()


def load_session_config(
    prompt: str,
    width: int,
    height: int,
    session_config_path: Path | None,
) -> dict:
    if session_config_path is None:
        return {
            "prompt": prompt,
            "width": width,
            "height": height,
        }

    with session_config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    if not isinstance(config, dict):
        raise ValueError("Session config JSON must be an object")

    return config


async def stream_frames(
    ws_url: str,
    image_path: Path,
    session_config: dict,
    fps: float,
    frame_count: int | None,
    save_dir: Path | None,
) -> None:
    from websockets.asyncio.client import connect

    width = int(session_config["width"])
    height = int(session_config["height"])

    with Image.open(image_path) as source:
        image = source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=88)
        encoded = buffer.getvalue()

    frame_interval = 1.0 / fps
    frames_sent = 0

    async with connect(ws_url, max_size=32_000_000) as websocket:
        ready = await websocket.recv()
        print(ready)
        await websocket.send(
            json.dumps(
                {
                    "type": "session.update",
                    "config": session_config,
                }
            )
        )
        while frame_count is None or frames_sent < frame_count:
            started = time.perf_counter()
            frame_id = str(uuid.uuid4())
            await websocket.send(
                json.dumps(
                    {
                        "type": "frame.begin",
                        "frame_id": frame_id,
                        "image_format": "jpeg",
                    }
                )
            )
            await websocket.send(encoded)
            while True:
                raw = await websocket.recv()
                if isinstance(raw, bytes):
                    if save_dir is not None:
                        save_dir.mkdir(parents=True, exist_ok=True)
                        output_path = save_dir / f"{frame_id}.jpg"
                        output_path.write_bytes(raw)
                        print(f"saved_output={output_path}")
                    break

                message = json.loads(raw)
                if message.get("type") == "frame.result" and message.get("frame_id") == frame_id:
                    print(f"frame={message['frame_id']} latency_ms={message['latency_ms']:.1f}")

            frames_sent += 1
            elapsed = time.perf_counter() - started
            await asyncio.sleep(max(0.0, frame_interval - elapsed))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/ws/demo")
    parser.add_argument("--image", required=True)
    parser.add_argument("--prompt", default="neon smoke")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--fps", type=float, default=4.0)
    parser.add_argument("--session-id", default="demo")
    parser.add_argument("--session-config")
    parser.add_argument("--count", type=int)
    parser.add_argument("--save-dir")
    args = parser.parse_args()

    session_config = load_session_config(
        prompt=args.prompt,
        width=args.width,
        height=args.height,
        session_config_path=Path(args.session_config) if args.session_config else None,
    )

    create_session(args.base_url, args.session_id, session_config)
    asyncio.run(
        stream_frames(
            ws_url=args.ws_url,
            image_path=Path(args.image),
            session_config=session_config,
            fps=args.fps,
            frame_count=args.count,
            save_dir=Path(args.save_dir) if args.save_dir else None,
        )
    )


if __name__ == "__main__":
    main()
