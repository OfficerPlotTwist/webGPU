"""
TouchDesigner Script TOP decoder for frames returned from the rented GPU relay.

Use this in a Script TOP's callbacks DAT.

Expected companion operators:
    Text DAT:  latest_frame_b64
    Text DAT:  latest_frame_meta

Optional:
    Table DAT: relay_status

What it does:
    - reads the most recent base64-encoded output frame from latest_frame_b64
    - decodes JPEG/PNG bytes with PIL
    - copies the resulting image into the Script TOP via copyNumpyArray()
    - avoids redundant decode work when the frame_id has not changed

Recommended network:
    webSocket DAT -> remote_ws_callbacks.py -> latest_frame_b64/latest_frame_meta -> Script TOP
"""

import base64
import io
import json

import numpy as np
from PIL import Image


def onSetupParameters(scriptOp):
    page = scriptOp.appendCustomPage("Relay")
    page.appendPulse("Reload", label="Reload")
    return


def onPulse(par):
    if par.name == "Reload":
        target = par.owner
        target.store("relay_last_frame_id", None)
    return


def onCook(scriptOp):
    meta_dat = op("latest_frame_meta")
    image_dat = op("latest_frame_b64")

    if meta_dat is None or image_dat is None:
        _fill_placeholder(scriptOp, "Missing latest_frame_meta/latest_frame_b64")
        return

    meta_text = meta_dat.text.strip()
    image_b64 = image_dat.text.strip()

    if not meta_text or not image_b64:
        _fill_placeholder(scriptOp, "Waiting for remote frame")
        return

    try:
        meta = json.loads(meta_text)
    except Exception as exc:
        _set_status("decoder_error", "meta json failed: {}".format(exc))
        _fill_placeholder(scriptOp, "Invalid frame metadata")
        return

    frame_id = meta.get("frame_id", "")
    last_frame_id = scriptOp.fetch("relay_last_frame_id", None)
    cached_frame = scriptOp.fetch("relay_cached_frame", None)

    if frame_id and frame_id == last_frame_id and cached_frame is not None:
        scriptOp.copyNumpyArray(cached_frame)
        return

    try:
        raw_bytes = base64.b64decode(image_b64)
        pil_image = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
        np_image = np.asarray(pil_image).astype(np.uint8)
    except Exception as exc:
        _set_status("decoder_error", "image decode failed: {}".format(exc))
        _fill_placeholder(scriptOp, "Frame decode failed")
        return

    scriptOp.copyNumpyArray(np_image)
    scriptOp.store("relay_last_frame_id", frame_id)
    scriptOp.store("relay_cached_frame", np_image)
    _set_status("decoder_last_frame_id", frame_id)
    _set_status("decoder_last_latency_ms", str(meta.get("latency_ms", "")))
    return


def _fill_placeholder(scriptOp, label):
    height = 64
    width = 64
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[:, :, 3] = 255
    image[:, :, 0] = 24
    image[:, :, 1] = 24
    image[:, :, 2] = 24
    scriptOp.copyNumpyArray(image)
    _set_status("decoder_state", label)


def _set_status(key, value):
    table = op("relay_status")
    if table is None:
        return

    if table.numRows == 0:
        table.appendRow(["key", "value"])

    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            table[row, 1] = value
            return

    table.appendRow([key, value])
