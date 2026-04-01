import json
import urllib.request


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_SESSION_ID = "show-main"


def post_offer(offer_sdp, base_url=DEFAULT_BASE_URL, session_id=DEFAULT_SESSION_ID):
    payload = {
        "sdp": str(offer_sdp),
        "type": "offer",
    }
    return _http_json(
        "POST",
        "{}/sessions/{}/webrtc/offer".format(base_url.rstrip("/"), session_id),
        payload,
    )


def post_candidate(candidate, sdp_mid=None, sdp_mline_index=None, base_url=DEFAULT_BASE_URL, session_id=DEFAULT_SESSION_ID):
    payload = {
        "candidate": {
            "candidate": str(candidate),
            "sdpMid": sdp_mid,
            "sdpMLineIndex": sdp_mline_index,
        }
    }
    return _http_json(
        "POST",
        "{}/sessions/{}/webrtc/candidate".format(base_url.rstrip("/"), session_id),
        payload,
    )


def set_status(key, value):
    table = op("relay_status")
    if table is None:
        return
    if table.numRows == 0:
        table.appendRow(["key", "value"])
    for row in range(1, table.numRows):
        if table[row, 0].val == key:
            table[row, 1] = str(value)
            return
    table.appendRow([key, str(value)])


def _http_json(method, url, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))
