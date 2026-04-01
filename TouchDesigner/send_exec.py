def onOffToOn(channel, sampleIndex, val, prev):
    sender = op("relay_sender")
    if sender is not None and hasattr(sender.module, "request_send"):
        sender.module.request_send()
    return


def onValueChange(channel, sampleIndex, val, prev):
    sender = op("relay_sender")
    if sender is not None and hasattr(sender.module, "request_send"):
        sender.module.request_send()
    return
