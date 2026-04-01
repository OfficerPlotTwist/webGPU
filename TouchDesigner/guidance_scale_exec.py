def onValueChange(channel, sampleIndex, val, prev):
    ws = op("ws_relay")
    callbacks = op("ws_relay_callbacks")
    status = op("relay_status")

    if ws is None or callbacks is None:
        return

    scale = max(0.0, float(val))

    if status is not None:
        _set_status(status, "guidance_scale", "{:.3f}".format(scale))

    callbacks.module.send_guidance_scale_update(ws, scale)
    return


def _set_status(table, key, value):
    if table.numRows == 0:
        table.appendRow(["key", "value"])

    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            table[row, 1] = value
            return

    table.appendRow([key, value])
