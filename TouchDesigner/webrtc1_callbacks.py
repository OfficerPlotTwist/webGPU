def start_connection():
    webrtc = op("webrtc1")
    signaling = op("webrtc_signaling")
    if webrtc is None or signaling is None:
        return None

    signaling.module.set_status("webrtc_error", "")
    signaling.module.set_status("webrtc_track_id", "")
    signaling.module.set_status("webrtc_track_type", "")
    connection_id = webrtc.openConnection()
    if not connection_id:
        signaling.module.set_status("webrtc_error", "openConnection failed")
        return None

    parent().store("webrtc_connection_id", connection_id)
    signaling.module.set_status("webrtc_connection_id", connection_id)
    signaling.module.set_status("webrtc_state", "opening")
    webrtc.createOffer(connection_id)
    return connection_id


def apply_answer(answer):
    webrtc = op("webrtc1")
    signaling = op("webrtc_signaling")
    connection_id = parent().fetch("webrtc_connection_id", None)
    if webrtc is None or signaling is None or not connection_id:
        return

    try:
        webrtc.setRemoteDescription(connection_id, answer.get("type", "answer"), answer.get("sdp", ""))
        signaling.module.set_status("webrtc_state", "answer_applied")
    except Exception as exc:
        signaling.module.set_status("webrtc_error", str(exc))


def onOffer(webrtcDAT, connectionId, localSdp):
    signaling = op("webrtc_signaling")
    if signaling is None:
        return

    try:
        webrtcDAT.setLocalDescription(connectionId, "offer", localSdp, stereo=False)
        signaling.module.set_status("webrtc_local_sdp_len", len(localSdp or ""))
        answer = signaling.module.post_offer(localSdp)
        signaling.module.set_status("webrtc_state", "offer_sent")
        apply_answer(answer)
    except Exception as exc:
        signaling.module.set_status("webrtc_error", str(exc))
        signaling.module.set_status("webrtc_state", "offer_failed")
    return


def onAnswer(webrtcDAT, connectionId, localSdp):
    signaling = op("webrtc_signaling")
    if signaling is None:
        return

    webrtcDAT.setLocalDescription(connectionId, "answer", localSdp, stereo=False)
    signaling.module.set_status("webrtc_state", "answer_created")
    return


def onNegotiationNeeded(webrtcDAT, connectionId):
    signaling = op("webrtc_signaling")
    if signaling is not None:
        signaling.module.set_status("webrtc_negotiation", connectionId)
    return


def onIceCandidate(webrtcDAT, connectionId, candidate, lineIndex, sdpMid):
    signaling = op("webrtc_signaling")
    if signaling is None:
        return
    try:
        signaling.module.post_candidate(candidate, sdpMid, lineIndex)
        signaling.module.set_status("webrtc_last_candidate", candidate[:64])
    except Exception as exc:
        signaling.module.set_status("webrtc_error", str(exc))
    return


def onIceCandidateError(webrtcDAT, connectionId, errorText):
    signaling = op("webrtc_signaling")
    if signaling is not None:
        signaling.module.set_status("webrtc_error", errorText)
    return


def onTrack(webrtcDAT, connectionId, trackId, type):
    signaling = op("webrtc_signaling")
    if signaling is not None:
        signaling.module.set_status("webrtc_track_id", trackId)
        signaling.module.set_status("webrtc_track_type", type)
        signaling.module.set_status("webrtc_state", "track")

    video_in = op("webrtc_video_in")
    if video_in is not None and type == "video":
        try:
            video_in.par.webrtc = "webrtc1"
            video_in.par.webrtcconnection = connectionId
            video_in.par.webrtctrack = trackId
            video_in.par.active = True
        except Exception:
            pass
    return


def onRemoveTrack(webrtcDAT, connectionId, trackId, type):
    signaling = op("webrtc_signaling")
    if signaling is not None:
        signaling.module.set_status("webrtc_track_removed", trackId)
    return


def onDataChannel(webrtcDAT, connectionId, channelName):
    return


def onDataChannelOpen(webrtcDAT, connectionId, channelName):
    return


def onDataChannelClose(webrtcDAT, connectionId, channelName):
    return


def onData(webrtcDAT, connectionId, channelName, data):
    return


def onConnectionStateChange(webrtcDAT, connectionId, newState):
    signaling = op("webrtc_signaling")
    if signaling is not None:
        signaling.module.set_status("webrtc_state", newState)
    return


def onSignalingStateChange(webrtcDAT, connectionId, newState):
    signaling = op("webrtc_signaling")
    if signaling is not None:
        signaling.module.set_status("webrtc_signaling_state", newState)
    return


def onIceConnectionStateChange(webrtcDAT, connectionId, newState):
    signaling = op("webrtc_signaling")
    if signaling is not None:
        signaling.module.set_status("webrtc_ice_state", newState)
    return


def onIceGatheringStateChange(webrtcDAT, connectionId, newState):
    signaling = op("webrtc_signaling")
    if signaling is not None:
        signaling.module.set_status("webrtc_ice_gathering_state", newState)
    return
