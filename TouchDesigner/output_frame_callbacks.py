import base64
import json

import cv2
import numpy as np


def onGetCookLevel(scriptOp):
    return CookLevel.AUTOMATIC


def onCook(scriptOp):
    base = scriptOp.parent()
    meta_dat = base.op("latest_frame_meta") if base is not None else None
    image_dat = base.op("latest_frame_b64") if base is not None else None

    if meta_dat is None or image_dat is None:
        _fill_placeholder(scriptOp)
        _set_status(base, "decoder_state", "Missing latest_frame_meta/latest_frame_b64")
        return

    meta_text = meta_dat.text.strip()
    image_b64 = image_dat.text.strip()
    if not meta_text or not image_b64:
        _fill_placeholder(scriptOp)
        _set_status(base, "decoder_state", "Waiting for remote frame")
        return

    try:
        meta = json.loads(meta_text)
    except Exception as exc:
        _fill_placeholder(scriptOp)
        _set_status(base, "decoder_error", "meta json failed: {}".format(exc))
        _set_status(base, "decoder_state", "Invalid frame metadata")
        return

    try:
        raw_bytes = base64.b64decode(image_b64)
        encoded = np.frombuffer(raw_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
        if decoded is None:
            raise ValueError("cv2.imdecode returned None")
        if decoded.ndim == 2:
            rgb = cv2.cvtColor(decoded, cv2.COLOR_GRAY2RGB)
        elif decoded.shape[2] == 3:
            rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
        elif decoded.shape[2] == 4:
            rgb = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGB)
        else:
            raise ValueError("unexpected decoded shape: {}".format(decoded.shape))
    except Exception as exc:
        _fill_placeholder(scriptOp)
        _set_status(base, "decoder_error", "image decode failed: {}".format(exc))
        _set_status(base, "decoder_state", "Frame decode failed")
        return

    scriptOp.copyNumpyArray(np.ascontiguousarray(rgb.astype(np.uint8)))
    _set_status(base, "decoder_state", "Frame received")
    _set_status(base, "decoder_last_frame_id", str(meta.get("frame_id", "")))
    _set_status(base, "decoder_last_latency_ms", str(meta.get("latency_ms", "")))


def _fill_placeholder(scriptOp):
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[:, :, 0] = 24
    image[:, :, 1] = 24
    image[:, :, 2] = 24
    scriptOp.copyNumpyArray(image)


def _set_status(base, key, value):
    if base is None:
        return
    table = base.op("relay_status")
    if table is None:
        return
    if table.numRows == 0:
        table.appendRow(["key", "value"])
    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            table[row, 1] = value
            return
    table.appendRow([key, value])
