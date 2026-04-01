def onValueChange(channel, sampleIndex, val, prev):
    table = op("prompt_table")
    ws = op("ws_relay")
    callbacks = op("ws_relay_callbacks")

    if table is None or ws is None or callbacks is None:
        return

    prompt_count = max(0, table.numRows - 1)
    if prompt_count <= 0:
        return

    index = int(round(val)) % prompt_count
    row = index + 1
    prompt = table[row, 0].val.strip()
    negative_prompt = ""
    if table.numCols > 1:
        negative_prompt = table[row, 1].val.strip()

    if not prompt:
        return

    callbacks.module.send_prompt_update(ws, prompt, negative_prompt or None)

    status = op("relay_status")
    if status is not None:
        _set_status(status, "prompt_index", str(index))
        _set_status(status, "active_prompt", prompt)
        _set_status(status, "active_negative_prompt", negative_prompt)

    return


def _set_status(table, key, value):
    if table.numRows == 0:
        table.appendRow(["key", "value"])

    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            table[row, 1] = value
            return

    table.appendRow([key, value])
