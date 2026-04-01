from __future__ import annotations

import argparse
import asyncio
import io
import json
import time
import urllib.request
import uuid
from pathlib import Path

from aiortc import RTCPeerConnection, RTCSessionDescription
from PIL import Image


def http_json(method: str, url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def load_session_payload(config_path: Path, session_id: str) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload["session_id"] = session_id
    payload.setdefault("config", {})
    payload["config"]["output_transport"] = "webrtc"
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


async def run_probe(base_url: str, ws_url: str, session_payload: dict, output_path: Path | None) -> None:
    from websockets.asyncio.client import connect

    created = http_json("POST", f"{base_url}/sessions", session_payload)
    print(f"session_created={created['session_id']} backend={created['backend']}")

    video_event = asyncio.Event()
    pc = RTCPeerConnection()

    @pc.on("track")
    def on_track(track) -> None:
        if track.kind != "video":
            return

        async def consume() -> None:
            frame = await track.recv()
            image = frame.to_image()
            if output_path is not None:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path)
            print(f"webrtc_frame={image.size[0]}x{image.size[1]}")
            video_event.set()

        asyncio.create_task(consume())

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    answer = http_json(
        "POST",
        f"{base_url}/sessions/{session_payload['session_id']}/webrtc/offer",
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
    )
    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
    print("webrtc_connected=answer_applied")

    width = int(session_payload["config"]["width"])
    height = int(session_payload["config"]["height"])
    probe = build_probe_frame(width, height)

    async with connect(ws_url, max_size=32_000_000) as websocket:
        ready_raw = await websocket.recv()
        print(f"session_ready={ready_raw}")
        frame_id = str(uuid.uuid4())
        started = time.perf_counter()
        await websocket.send(json.dumps({"type": "frame.begin", "frame_id": frame_id, "image_format": "jpeg"}))
        await websocket.send(probe)

        while True:
            raw = await websocket.recv()
            if isinstance(raw, bytes):
                print(f"unexpected_binary_bytes={len(raw)}")
                break
            message = json.loads(raw)
            if message.get("type") == "frame.result" and message.get("frame_id") == frame_id:
                print(f"frame_result={json.dumps(message)}")
                break

        await asyncio.wait_for(video_event.wait(), timeout=10.0)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        print(f"webrtc_elapsed_ms={elapsed_ms:.1f}")

    await pc.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the WebRTC output transport.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/ws/show-main")
    parser.add_argument("--session-config", default="configs/show-main.session.json")
    parser.add_argument("--session-id", default="show-main")
    parser.add_argument("--save-output")
    args = parser.parse_args()

    session_payload = load_session_payload(Path(args.session_config), args.session_id)
    asyncio.run(
        run_probe(
            base_url=args.base_url,
            ws_url=args.ws_url,
            session_payload=session_payload,
            output_path=Path(args.save_output) if args.save_output else None,
        )
    )


if __name__ == "__main__":
    main()
