def onOffToOn(channel, sampleIndex, val, prev):
    sender = op("relay_sender")
    if sender is not None:
        sender.module.send_latest_frame()
    return


def onValueChange(channel, sampleIndex, val, prev):
    sender = op("relay_sender")
    if sender is not None:
        sender.module.send_latest_frame()
    return
