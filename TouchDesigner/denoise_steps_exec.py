def onValueChange(channel, sampleIndex, val, prev):
    ws = op("ws_relay")
    callbacks = op("ws_relay_callbacks")
    status = op("relay_status")

    if ws is None or callbacks is None:
        return

    steps = min(8, max(1, int(round(val))))

    if status is not None:
        _set_status(status, "denoise_steps", str(steps))

    callbacks.module.send_denoise_steps_update(ws, steps)
    return


def _set_status(table, key, value):
    if table.numRows == 0:
        table.appendRow(["key", "value"])

    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            table[row, 1] = value
            return

    table.appendRow([key, value])
