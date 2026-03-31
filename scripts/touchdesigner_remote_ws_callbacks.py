"""
TouchDesigner WebSocket DAT callbacks for the rented GPU relay.

Use this with a `webSocket DAT` that connects directly to:
    ws://<gpu-host>:8000/ws/<session_id>

Recommended operator names:
    webSocket DAT:   ws_relay
    Table DAT:       relay_status
    Text DAT:        latest_frame_b64
    Text DAT:        latest_frame_meta
    CHOP/DAT target: frame_ready   (optional pulse target)

Paste this file into the callback DAT for the WebSocket DAT.

Important:
TouchDesigner callback signatures can vary slightly by build/template.
If your generated callback template differs, keep the function bodies and
adapt only the argument list to match the template TouchDesigner creates.
"""

import base64
import json
import time
import uuid


DEFAULT_CONFIG = {
    "prompt": "neon fog, live abstract video feedback",
    "negative_prompt": "muddy, blurry, low detail",
    "model_id_or_path": "stabilityai/sdxl-turbo",
    "width": 512,
    "height": 512,
    "guidance_scale": 0.0,
    "delta": 1.0,
    "denoise_steps": 1,
    "seed": 2416333,
    "scheduler_name": "Euler",
    "frame_buffer_size": 1,
    "use_denoising_batch": True,
    "acceleration": "none",
    "mode": "img2img",
    "output_format": "jpeg",
    "jpeg_quality": 88,
}


def onConnect(dat):
    _set_status("connected", "1")
    _set_status("connected_at", str(time.time()))
    send_session_update(dat, DEFAULT_CONFIG)
    return


def onDisconnect(dat):
    _set_status("connected", "0")
    _set_status("last_disconnect", str(time.time()))
    return


def onReceiveText(dat, rowIndex, message, byteData):
    try:
        payload = json.loads(message)
    except Exception as exc:
        _set_status("last_error", "invalid_json: {}".format(exc))
        return

    msg_type = payload.get("type", "")
    _set_status("last_message_type", msg_type)
    _set_status("last_message_at", str(time.time()))

    if msg_type == "session.ready":
        _set_status("backend", payload.get("backend", ""))
        _set_status("session_id", payload.get("session_id", ""))
        return

    if msg_type == "session.updated":
        _write_text_dat("latest_frame_meta", json.dumps(payload, indent=2))
        return

    if msg_type == "frame.result":
        _store_frame_meta(payload)
        return

    if msg_type == "frame.error":
        _set_status("last_error", payload.get("error", "unknown frame error"))
        return

    if msg_type == "session.metrics":
        metrics = payload.get("metrics", {})
        for key, value in metrics.items():
            _set_status("metric_{}".format(key), str(value))
        return

    if msg_type == "pong":
        _set_status("last_pong", str(time.time()))
        return

    _write_text_dat("latest_frame_meta", json.dumps(payload, indent=2))
    return


def onReceiveBinary(dat, rowIndex, message, byteData):
    _set_status("last_binary_message_at", str(time.time()))
    _store_frame_binary(byteData)
    return


def onMonitorMessage(dat, message):
    _set_status("monitor", str(message))
    return


def send_ping(dat):
    dat.sendText(json.dumps({"type": "ping"}))


def send_session_update(dat, config):
    payload = {
        "type": "session.update",
        "config": config,
    }
    dat.sendText(json.dumps(payload))
    _set_status("last_config_push", str(time.time()))


def send_prompt_update(dat, prompt, negative_prompt=None):
    config = dict(DEFAULT_CONFIG)
    config["prompt"] = prompt
    if negative_prompt is not None:
        config["negative_prompt"] = negative_prompt
    send_session_update(dat, config)


def send_frame_bytes(dat, image_bytes, image_format="jpeg", settings=None, frame_id=None):
    frame_id = frame_id or str(uuid.uuid4())
    payload = {
        "type": "frame.begin",
        "frame_id": frame_id,
        "image_format": image_format,
    }
    dat.sendText(json.dumps(payload))
    _send_binary(dat, image_bytes)
    if settings:
        _set_status("pending_settings_note", json.dumps(settings))
    _set_status("last_frame_id", frame_id)
    _set_status("last_frame_submit", str(time.time()))


def send_frame_from_text_dat(dat, source_text_dat, image_format="jpeg", settings=None, frame_id=None):
    source = op(source_text_dat)
    if source is None:
        _set_status("last_error", "missing source text DAT: {}".format(source_text_dat))
        return
    raw = source.text.strip()
    if not raw:
        _set_status("last_error", "empty source text DAT: {}".format(source_text_dat))
        return
    try:
        image_bytes = base64.b64decode(raw)
    except Exception as exc:
        _set_status("last_error", "base64 decode failed: {}".format(exc))
        return
    send_frame_bytes(dat, image_bytes, image_format=image_format, settings=settings, frame_id=frame_id)


def _store_frame_meta(payload):
    meta = {
        "frame_id": payload.get("frame_id", ""),
        "image_format": payload.get("image_format", ""),
        "latency_ms": payload.get("latency_ms", None),
        "queue_depth": payload.get("queue_depth", None),
        "received_at": time.time(),
    }
    _write_text_dat("latest_frame_meta", json.dumps(meta, indent=2))

    _set_status("last_result_frame_id", meta["frame_id"])
    _set_status("last_latency_ms", str(meta["latency_ms"]))
    _set_status("last_queue_depth", str(meta["queue_depth"]))


def _store_frame_binary(byte_data):
    if byte_data is None:
        return
    encoded = base64.b64encode(byte_data).decode("ascii")
    _write_text_dat("latest_frame_b64", encoded)

    pulse_target = op("frame_ready")
    if pulse_target is not None:
        try:
            pulse_target.par.pulse.pulse()
        except Exception:
            pass


def _write_text_dat(name, value):
    target = op(name)
    if target is not None:
        target.text = value


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


def _send_binary(dat, payload):
    if hasattr(dat, "sendBytes"):
        dat.sendBytes(payload)
        return
    if hasattr(dat, "sendBinary"):
        dat.sendBinary(payload)
        return
    raise AttributeError("WebSocket DAT does not expose sendBytes/sendBinary on this build")
