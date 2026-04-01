def onValueChange(channel, sampleIndex, val, prev):
    ws = op("ws_relay")
    callbacks = op("ws_relay_callbacks")
    controls = op("diffusion_controls")
    status = op("relay_status")

    if ws is None or callbacks is None or controls is None:
        return

    denoise_steps = _read_channel(controls, "denoise_steps", default=2.0)
    denoise_steps = min(8, max(1, int(round(denoise_steps))))

    guidance_scale = _read_channel(controls, "guidance_scale", default=0.0)
    guidance_scale = max(0.0, float(guidance_scale))

    delta = _read_channel(controls, "delta", default=1.0)
    delta = max(0.0, float(delta))

    tindexblock0step = _read_channel(controls, "tindexblock0step", default=32.0)
    tindexblock0step = min(45, max(0, int(round(tindexblock0step))))

    if status is not None:
        _set_status(status, "denoise_steps", str(denoise_steps))
        _set_status(status, "guidance_scale", "{:.3f}".format(guidance_scale))
        _set_status(status, "delta", "{:.3f}".format(delta))
        _set_status(status, "tindexblock0step", str(tindexblock0step))

    callbacks.module.send_diffusion_controls_update(
        ws,
        denoise_steps=denoise_steps,
        guidance_scale=guidance_scale,
        delta=delta,
        tindexblock0step=tindexblock0step,
    )
    return


def _read_channel(chop, name, default=0.0):
    try:
        return float(chop[name][0])
    except Exception:
        return default


def _set_status(table, key, value):
    if table.numRows == 0:
        table.appendRow(["key", "value"])

    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            table[row, 1] = value
            return

    table.appendRow([key, value])
