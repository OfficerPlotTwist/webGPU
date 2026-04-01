Use operator-specific TouchDesigner callback contracts exactly as documented for the operator type.

Rules:
- Treat repo `.py` files as the source of truth, then reload them through the corresponding `*_path` / synced DAT in TouchDesigner.
- Preserve required built-in callback functions for the operator type. Examples:
  - `scriptTOP`: keep `onGetCookLevel(scriptOp)` and `onCook(scriptOp)`
  - `websocketDAT`: use the documented websocket callback names/signatures for that build
- Verify callback signatures against official Derivative docs and the local `td_python_api.json` before changing them.
- Do not infer callback signatures from other DAT/TOP operator families.

Current verified callbacks in this project:
- `output_frame_callbacks.py`
  - `onGetCookLevel(scriptOp)`
  - `onCook(scriptOp)`
- `ws_relay_callbacks.py`
  - `onConnect(dat)`
  - `onDisconnect(dat)`
  - `onReceiveText(dat, rowIndex, message, *extra)`
  - `onReceiveBinary(dat, contents, *extra)`
  - `onMonitorMessage(dat, message)`
  - `onReceivePing(dat, contents)`
  - `onReceivePong(dat, contents)`

Workflow:
1. Edit the repo file.
2. Pulse the TouchDesigner DAT reload/refresh.
3. Check the live operator error state.
4. Validate side effects in `relay_status`, `latest_frame_meta`, and `latest_frame_b64`.

For `websocketDAT` in this project:
- `bytes` must be enabled.
- Binary image payloads are expected after `frame.result`.
- Proof of a good binary receive is:
  - `relay_status['last_binary_payload_size'] > 0`
  - `relay_status['last_binary_prefix_hex']` starts with a JPEG/PNG signature
  - `latest_frame_b64` is non-empty
