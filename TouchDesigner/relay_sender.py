import json
import time
import uuid

import cv2
import numpy as np


SEND_TOP = "send_fit"
WS_DAT = "ws_relay"
JPEG_QUALITY = 75
TARGET_FPS = 4.0
STALE_TIMEOUT_SEC = 3.0


def send_latest_frame():
    if _is_busy():
        return False

    ws = op(WS_DAT)
    top = op(SEND_TOP)
    if ws is None or top is None:
        return False

    arr = top.numpyArray(delayed=True)
    if arr is None or arr.ndim != 3:
        return False

    if arr.dtype != np.uint8:
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)

    if arr.shape[2] == 4:
        arr = arr[:, :, :3]

    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    ok, encoded = cv2.imencode(
        ".jpg",
        bgr,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(JPEG_QUALITY)],
    )
    if not ok:
        raise RuntimeError("cv2.imencode failed for relay_sender")

    frame_id = str(uuid.uuid4())
    ws.sendText(
        json.dumps(
            {
                "type": "frame.begin",
                "frame_id": frame_id,
                "image_format": "jpeg",
            }
        )
    )
    _send_binary(ws, encoded.tobytes())

    parent().store("relay_in_flight", True)
    parent().store("relay_last_frame_id", frame_id)
    parent().store("relay_last_sent_at", time.time())
    _set_status("relay_mode", "one_in_flight")
    _set_status("relay_last_send_result", "sent")
    return True


def mark_result_received():
    parent().store("relay_in_flight", False)
    parent().store("relay_last_result_at", time.time())
    _set_status("relay_last_send_result", "received")


def _is_busy():
    comp = parent()
    in_flight = comp.fetch("relay_in_flight", False)
    last_sent = comp.fetch("relay_last_sent_at", 0.0)
    if in_flight and last_sent and (time.time() - last_sent) > STALE_TIMEOUT_SEC:
        comp.store("relay_in_flight", False)
        _set_status("relay_last_send_result", "timeout_reset")
        _set_status("relay_timeout_reset_at", str(time.time()))
        in_flight = False
    min_interval = 1.0 / TARGET_FPS
    return in_flight or (time.time() - last_sent) < min_interval


def _set_status(key, value):
    table = op("relay_status")
    if table is None:
        return
    if table.numRows == 0:
        table.appendRow(["key", "value"])
    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            table[row, 1] = str(value)
            return
    table.appendRow([key, str(value)])


def _send_binary(dat, payload):
    if hasattr(dat, "sendBytes"):
        dat.sendBytes(payload)
        return
    if hasattr(dat, "sendBinary"):
        dat.sendBinary(payload)
        return
    raise AttributeError("WebSocket DAT does not expose sendBytes/sendBinary on this build")
