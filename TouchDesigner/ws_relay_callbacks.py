import base64
import json
import time
import uuid


DEFAULT_CONFIG = {
    "prompt": "neon fog, live abstract video feedback",
    "negative_prompt": "muddy, blurry, low detail",
    "model_id_or_path": "stabilityai/sd-turbo",
    "width": 256,
    "height": 256,
    "guidance_scale": 0.0,
    "delta": 1.0,
    "denoise_steps": 2,
    "seed": 2416333,
    "scheduler_name": "Euler",
    "frame_buffer_size": 1,
    "use_denoising_batch": True,
    "acceleration": "none",
    "mode": "img2img",
    "output_format": "jpeg",
    "jpeg_quality": 88,
    "output_transport": "webrtc",
}


def onConnect(dat):
    _set_status("connected", "1")
    _set_status("connected_at", str(time.time()))
    send_session_update(dat, _build_current_config())
    return


def onDisconnect(dat):
    _set_status("connected", "0")
    _set_status("last_disconnect", str(time.time()))
    sender = op("relay_sender")
    if sender is not None:
        if hasattr(sender.module, "mark_disconnected"):
            sender.module.mark_disconnected()
        elif hasattr(sender.module, "mark_result_received"):
            sender.module.mark_result_received()
    return


def onReceiveText(dat, rowIndex, message, *extra):
    _set_status("text_row_index", str(rowIndex))
    _set_status("text_message_type", str(type(message).__name__))
    if extra:
        byte_data = extra[0]
        _set_status("text_byteData_type", str(type(byte_data).__name__))
        if byte_data is not None:
            try:
                _set_status("text_byteData_size", str(len(byte_data)))
            except Exception:
                _set_status("text_byteData_size", "len_error")

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
        _write_text_dat("latest_session_config", json.dumps(payload, indent=2))
        return

    if msg_type == "frame.result":
        _store_frame_meta(payload)
        sender = op("relay_sender")
        if sender is not None and hasattr(sender.module, "mark_result_received"):
            sender.module.mark_result_received()
        return

    if msg_type == "frame.error":
        _set_status("last_error", payload.get("error", "unknown frame error"))
        sender = op("relay_sender")
        if sender is not None and hasattr(sender.module, "mark_result_received"):
            sender.module.mark_result_received()
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


def onReceiveBinary(dat, contents, *extra):
    _set_status("last_binary_message_at", str(time.time()))
    payload = contents
    if payload is None and extra and isinstance(extra[0], (bytes, bytearray)):
        payload = bytes(extra[0])
    _set_status("last_binary_message_type", str(type(contents).__name__))
    _set_status("last_binary_payload_size", str(len(payload) if payload is not None else 0))
    if payload is not None:
        _set_status("last_binary_prefix_hex", payload[:8].hex())
    _store_frame_binary(payload)
    sender = op("relay_sender")
    if sender is not None and hasattr(sender.module, "mark_result_received"):
        sender.module.mark_result_received()
    return


def onReceivePing(dat, contents):
    _set_status("last_ping_at", str(time.time()))
    if hasattr(dat, "sendPong"):
        dat.sendPong(contents)
    return


def onReceivePong(dat, contents):
    _set_status("last_pong", str(time.time()))
    _set_status("last_pong_size", str(len(contents) if contents is not None else 0))
    return


def onMonitorMessage(dat, message):
    _set_status("monitor", str(message))
    return


def send_ping(dat):
    dat.sendText(json.dumps({"type": "ping"}))


def send_session_update(dat, config):
    dat.sendText(json.dumps({"type": "session.update", "config": config}))
    _set_status("last_config_push", str(time.time()))


def send_prompt_update(dat, prompt, negative_prompt=None):
    config = _build_current_config()
    config["prompt"] = prompt
    if negative_prompt is not None:
        config["negative_prompt"] = negative_prompt
    send_session_update(dat, config)


def send_denoise_steps_update(dat, denoise_steps):
    config = _build_current_config()
    config["denoise_steps"] = int(denoise_steps)
    send_session_update(dat, config)


def send_guidance_scale_update(dat, guidance_scale):
    config = _build_current_config()
    config["guidance_scale"] = float(guidance_scale)
    send_session_update(dat, config)


def send_frame_bytes(dat, image_bytes, image_format="jpeg", settings=None, frame_id=None):
    frame_id = frame_id or str(uuid.uuid4())
    dat.sendText(
        json.dumps(
            {
                "type": "frame.begin",
                "frame_id": frame_id,
                "image_format": image_format,
            }
        )
    )
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
    now = time.time()
    meta = {
        "frame_id": payload.get("frame_id", ""),
        "image_format": payload.get("image_format", ""),
        "latency_ms": payload.get("latency_ms", None),
        "queue_depth": payload.get("queue_depth", None),
        "received_at": now,
    }
    _write_text_dat("latest_frame_meta", json.dumps(meta, indent=2))
    _set_status("last_result_frame_id", meta["frame_id"])
    _set_status("last_latency_ms", str(meta["latency_ms"]))
    _set_status("last_queue_depth", str(meta["queue_depth"]))
    last_sent_at = _get_float_status("last_send_epoch", 0.0)
    if last_sent_at > 0.0:
        _set_status("last_result_roundtrip_ms", "{:.1f}".format((now - last_sent_at) * 1000.0))
    _set_status("last_result_received_at", str(now))


def _store_frame_binary(byte_data):
    if byte_data is None:
        _set_status("last_error", "binary callback fired without payload bytes")
        return
    started_at = time.perf_counter()
    encoded = base64.b64encode(byte_data).decode("ascii")
    _write_text_dat("latest_frame_b64", encoded)
    _set_status("latest_frame_b64_len", str(len(encoded)))
    _set_status("last_binary_store_ms", "{:.1f}".format((time.perf_counter() - started_at) * 1000.0))
    last_result_at = _get_float_status("last_result_received_at", 0.0)
    if last_result_at > 0.0:
        _set_status("result_to_binary_ms", "{:.1f}".format((time.time() - last_result_at) * 1000.0))


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


def _get_status(key, default=None):
    table = op("relay_status")
    if table is None:
        return default
    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            return table[row, 1].val
    return default


def _get_float_status(key, default=0.0):
    value = _get_status(key, None)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _build_current_config():
    config = dict(DEFAULT_CONFIG)

    active_prompt = _get_status("active_prompt", "")
    if active_prompt:
        config["prompt"] = active_prompt

    active_negative = _get_status("active_negative_prompt", "")
    if active_negative is not None and active_negative != "":
        config["negative_prompt"] = active_negative

    denoise_steps = _get_status("denoise_steps", "")
    if denoise_steps not in (None, ""):
        try:
            config["denoise_steps"] = min(8, max(1, int(round(float(denoise_steps)))))
        except Exception:
            pass

    guidance_scale = _get_status("guidance_scale", "")
    if guidance_scale not in (None, ""):
        try:
            config["guidance_scale"] = max(0.0, float(guidance_scale))
        except Exception:
            pass

    return config




def _send_binary(dat, payload):
    if hasattr(dat, "sendBytes"):
        dat.sendBytes(payload)
        return
    if hasattr(dat, "sendBinary"):
        dat.sendBinary(payload)
        return
    raise AttributeError("WebSocket DAT does not expose sendBytes/sendBinary on this build")
