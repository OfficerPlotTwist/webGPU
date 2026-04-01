from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.schemas import WebRTCCandidate

logger = logging.getLogger("live_diffusion.webrtc")

try:
    import av
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
    from aiortc.contrib.media import MediaRelay
    from aiortc.rtcicetransport import candidate_from_sdp
except ImportError:  # pragma: no cover - dependency availability is environment-specific
    av = None
    RTCPeerConnection = None
    RTCSessionDescription = None
    VideoStreamTrack = object
    MediaRelay = None
    candidate_from_sdp = None


class LatestFrameVideoTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self) -> None:
        super().__init__()
        self._frame_event = asyncio.Event()
        self._latest_frame: av.VideoFrame | None = None
        self._latest_monotonic = 0.0

    async def recv(self) -> av.VideoFrame:
        await self._frame_event.wait()
        frame = self._latest_frame
        if frame is None:
            await asyncio.sleep(0.005)
            return await self.recv()

        pts, time_base = await self.next_timestamp()
        clone = frame.reformat(format="rgb24")
        clone.pts = pts
        clone.time_base = time_base
        return clone

    def push_image(self, image: Image.Image) -> float:
        started = time.perf_counter()
        rgb = np.asarray(image.convert("RGB"))
        self._latest_frame = av.VideoFrame.from_ndarray(rgb, format="rgb24")
        self._latest_monotonic = time.monotonic()
        self._frame_event.set()
        return (time.perf_counter() - started) * 1000.0

    @property
    def last_frame_monotonic(self) -> float:
        return self._latest_monotonic


@dataclass(slots=True)
class WebRTCSession:
    session_id: str
    peer: RTCPeerConnection
    track: LatestFrameVideoTrack
    connected: bool = False
    last_state: str = "new"

    @classmethod
    def create(cls, session_id: str) -> "WebRTCSession":
        _ensure_webrtc_dependencies()
        peer = RTCPeerConnection()
        track = LatestFrameVideoTrack()
        relay = MediaRelay()
        peer.addTrack(relay.subscribe(track))
        session = cls(session_id=session_id, peer=peer, track=track)

        @peer.on("connectionstatechange")
        async def _on_connectionstatechange() -> None:
            session.last_state = peer.connectionState
            session.connected = peer.connectionState in {"connected", "completed"}
            logger.info(
                "webrtc.state session_id=%s state=%s",
                session_id,
                peer.connectionState,
            )

        return session

    async def apply_offer(self, sdp: str) -> RTCSessionDescription:
        _ensure_webrtc_dependencies()
        await self.peer.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
        answer = await self.peer.createAnswer()
        await self.peer.setLocalDescription(answer)
        assert self.peer.localDescription is not None
        logger.info("webrtc.answer session_id=%s", self.session_id)
        return self.peer.localDescription

    async def add_candidate(self, candidate: WebRTCCandidate) -> None:
        _ensure_webrtc_dependencies()
        ice = candidate_from_sdp(candidate.candidate)
        ice.sdpMid = candidate.sdpMid
        ice.sdpMLineIndex = candidate.sdpMLineIndex
        await self.peer.addIceCandidate(ice)

    async def close(self) -> None:
        await self.peer.close()
        self.connected = False
        self.last_state = "closed"


def _ensure_webrtc_dependencies() -> None:
    if RTCPeerConnection is None or RTCSessionDescription is None or av is None:
        raise RuntimeError(
            "WebRTC transport requires optional dependencies `aiortc` and `av`. "
            "Install the updated requirements before using output_transport='webrtc'."
        )
