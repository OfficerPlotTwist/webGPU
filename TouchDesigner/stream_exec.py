def onStart():
    return


def onCreate():
    return


def onExit():
    return


def onFrameStart(frame):
    sender = op("relay_sender")
    if sender is not None and hasattr(sender.module, "process_frame_tick"):
        sender.module.process_frame_tick()
    return


def onFrameEnd(frame):
    return


def onPlayStateChange(state):
    return


def onDeviceChange():
    return


def onProjectPreSave():
    return


def onProjectPostSave():
    return
