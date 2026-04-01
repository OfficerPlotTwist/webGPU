import json
import time
import uuid

import cv2
import numpy as np


SEND_TOP = "send_fit"
WS_DAT = "ws_relay"
JPEG_QUALITY = 75
TARGET_FPS = 3.0
SEND_TIMEOUT_SEC = 5.0


def send_latest_frame():
    request_send()
    return _flush_pending(force=True)


def request_send():
    parent().store("relay_pending_send", True)
    parent().store("relay_dirty", True)
    _set_status("relay_last_send_result", "queued")
    return True


def mark_result_received():
    parent().store("relay_last_result_at", time.time())
    parent().store("relay_in_flight", False)
    _set_status("relay_last_send_result", "received")
    _flush_pending()


def mark_disconnected():
    parent().store("relay_in_flight", False)
    _set_status("relay_last_send_result", "disconnected")


def process_frame_tick():
    return _flush_pending()


def _send_current_frame():
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
    parent().store("relay_pending_send", False)
    parent().store("relay_last_frame_id", frame_id)
    parent().store("relay_last_sent_at", time.time())
    _set_status("relay_mode", "latest_frame_queue")
    _set_status("relay_last_send_result", "sent")
    return True


def _flush_pending(force=False):
    if not parent().fetch("relay_pending_send", False):
        return False
    if _is_sending():
        return False
    if (not force) and _is_rate_limited():
        return False
    return _send_current_frame()


def _is_rate_limited():
    last_sent = parent().fetch("relay_last_sent_at", 0.0)
    min_interval = 1.0 / TARGET_FPS
    return (time.time() - last_sent) < min_interval


def _is_sending():
    if not parent().fetch("relay_in_flight", False):
        return False

    last_sent = parent().fetch("relay_last_sent_at", 0.0)
    if (time.time() - last_sent) > SEND_TIMEOUT_SEC:
        parent().store("relay_in_flight", False)
        _set_status("relay_last_send_result", "timeout_recovered")
        return False

    return True


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
