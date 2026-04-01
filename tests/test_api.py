from __future__ import annotations

import base64
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.server import app


def sample_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (64, 64), color=(128, 64, 255))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_warmup() -> None:
    client = TestClient(app)
    response = client.post("/warmup")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "model_id_or_path" in payload


def test_create_session_and_submit_frame() -> None:
    client = TestClient(app)
    created = client.post(
        "/sessions",
        json={"session_id": "test-session", "config": {"prompt": "fog", "width": 128, "height": 128}},
    )
    assert created.status_code == 200
    assert created.json()["session_id"] == "test-session"

    response = client.post(
        "/sessions/test-session/frames",
        json={
            "image_base64": base64.b64encode(sample_jpeg_bytes()).decode("ascii"),
            "image_format": "jpeg",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["image_format"] == "jpeg"
    assert payload["latency_ms"] >= 0


def test_websocket_binary_frame_roundtrip() -> None:
    client = TestClient(app)
    client.post(
        "/sessions",
        json={"session_id": "ws-session", "config": {"prompt": "fog", "width": 128, "height": 128}},
    )

    with client.websocket_connect("/ws/ws-session") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"

        websocket.send_json(
            {
                "type": "frame.begin",
                "frame_id": "frame-1",
                "image_format": "jpeg",
            }
        )
        websocket.send_bytes(sample_jpeg_bytes())

        result = websocket.receive_json()
        assert result["type"] == "frame.result"
        assert result["frame_id"] == "frame-1"

        output_bytes = websocket.receive_bytes()
        assert len(output_bytes) > 0


def test_webrtc_offer_endpoint() -> None:
    aiortc = pytest.importorskip("aiortc")
    RTCPeerConnection = aiortc.RTCPeerConnection
    RTCSessionDescription = aiortc.RTCSessionDescription
    client = TestClient(app)
    created = client.post(
        "/sessions",
        json={
            "session_id": "rtc-session",
            "config": {
                "prompt": "fog",
                "width": 128,
                "height": 128,
                "output_transport": "webrtc",
            },
        },
    )
    assert created.status_code == 200

    async def run_offer() -> None:
        pc = RTCPeerConnection()
        pc.addTransceiver("video", direction="recvonly")
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        response = client.post(
            "/sessions/rtc-session/webrtc/offer",
            json={"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "answer"
        await pc.setRemoteDescription(RTCSessionDescription(sdp=payload["sdp"], type=payload["type"]))
        await pc.close()

    import asyncio

    asyncio.run(run_offer())


def test_websocket_metadata_only_when_webrtc_transport_enabled() -> None:
    client = TestClient(app)
    client.post(
        "/sessions",
        json={
            "session_id": "webrtc-ws-session",
            "config": {
                "prompt": "fog",
                "width": 128,
                "height": 128,
                "output_transport": "webrtc",
            },
        },
    )

    with client.websocket_connect("/ws/webrtc-ws-session") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"

        websocket.send_json(
            {
                "type": "frame.begin",
                "frame_id": "frame-rtc-1",
                "image_format": "jpeg",
            }
        )
        websocket.send_bytes(sample_jpeg_bytes())

        result = websocket.receive_json()
        assert result["type"] == "frame.result"
        assert result["frame_id"] == "frame-rtc-1"
        # In webrtc mode without a connected peer, websocket fallback still returns binary bytes.
        output_bytes = websocket.receive_bytes()
        assert len(output_bytes) > 0
