PRINT_INTERVAL_SEC = 2.0


def onFrameStart(frame):
    comp = parent()
    now = absTime.seconds
    last_print = comp.fetch("textport_last_print_at", 0.0)
    if (now - last_print) < PRINT_INTERVAL_SEC:
        return

    comp.store("textport_last_print_at", now)

    status = op("relay_status")
    if status is None:
        print("[webgpu] relay_status missing")
        return

    connected = _status(status, "connected", "0") == "1"
    backend = _status(status, "backend", "?")
    processed = _as_int(_status(status, "metric_processed", "0"))
    last_processed = comp.fetch("textport_last_processed", processed)
    last_time = comp.fetch("textport_last_processed_at", now)

    elapsed = max(0.001, now - last_time)
    stream_fps = max(0.0, (processed - last_processed) / elapsed)

    comp.store("textport_last_processed", processed)
    comp.store("textport_last_processed_at", now)

    latency_ms = _status(status, "last_latency_ms", "-")
    send_state = _status(status, "relay_last_send_result", "-")
    decoder_error = _status(status, "decoder_error", "")
    decoder_state = _status(status, "decoder_state", "")
    frame_id = _status(status, "last_result_frame_id", "")
    prompt = _status(status, "active_prompt", "")
    delta = _status(status, "delta", "-")
    guidance_scale = _status(status, "guidance_scale", "-")
    denoise_steps = _status(status, "denoise_steps", "-")
    tindexblock0step = _status(status, "tindexblock0step", "-")
    connection_label = "OK" if connected else "DOWN"

    line = (
        "[webgpu] conn={conn} backend={backend} out_fps={fps:.2f} "
        "latency_ms={latency} send={send} "
        "delta={delta} g_scale={guidance} dnoise_steps={denoise} t0={t0}"
    ).format(
        conn=connection_label,
        backend=backend,
        fps=stream_fps,
        latency=latency_ms,
        send=send_state,
        delta=delta,
        guidance=guidance_scale,
        denoise=denoise_steps,
        t0=tindexblock0step,
    )
    if decoder_state:
        line += " decoder={}".format(decoder_state)
    if frame_id:
        line += " frame={}".format(frame_id[:8])
    if prompt:
        line += " prompt={}".format(_shorten(prompt, 64))
    if decoder_error and decoder_state != "Frame received":
        line += " decoder_error={}".format(decoder_error)
    print(line)
    return


def _status(table, key, default=""):
    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            return table[row, 1].val
    return default


def _as_int(value):
    try:
        return int(float(value))
    except Exception:
        return 0


def _shorten(text, max_len):
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
