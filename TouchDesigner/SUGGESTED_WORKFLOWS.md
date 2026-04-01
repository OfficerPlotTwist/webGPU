Suggested workflows based on the exact TouchDesigner + Runpod issues encountered in this project.

## 1. Callback-Signature Verification Workflow

Use this before changing any TD callback script.

Steps:
1. Identify the exact operator family first.
2. Check the local `td_python_api.json` and official Derivative docs for that operator's callback names/signatures.
3. Only then edit the repo `.py` file.
4. Reload the live DAT from file.
5. Confirm the live DAT text actually contains the expected functions.
6. Check the Error DAT after reload.

Why:
- We lost time by assuming `websocketDAT` callback signatures matched other DAT patterns.
- The fix was matching the actual live contract:
  - `onReceiveText(dat, rowIndex, message, *extra)`
  - `onReceiveBinary(dat, contents, *extra)`


## 2. File-Backed DAT Source-Of-Truth Workflow

Use repo files as source of truth, not the live DAT body.

Steps:
1. Edit the repo file under `TouchDesigner/`.
2. Reload via the corresponding DAT file parameter or `loadonstartpulse` / `refreshpulse`.
3. Verify the live DAT text matches the repo file.

Why:
- TD can keep stale text even after a file change if the DAT was not explicitly reloaded.
- We saw stale callback errors after the file had already been fixed.


## 3. Binary WebSocket Receive Verification Workflow

Use this when the server appears to process frames but TD does not display them.

Checks:
1. Confirm `frame.result` text arrives in `ws_relay`.
2. Confirm a binary row also appears in the `websocketDAT`.
3. Confirm callback side effects:
   - `relay_status['last_binary_payload_size']`
   - `relay_status['last_binary_prefix_hex']`
   - `relay_status['latest_frame_b64_len']`
4. Confirm `latest_frame_b64` is non-empty.
5. Confirm `output_frame` decodes and shows the returned image.

Why:
- The server was sending binary correctly.
- The real problem was the `websocketDAT` binary callback signature and latching path.


## 4. One-In-Flight Streaming Workflow

Treat live diffusion as latest-frame streaming with backpressure, not queued video delivery.

Rules:
- Only one frame may be in flight.
- Send the next frame only after a result arrives or a stale timeout clears the gate.
- Always send the newest current frame, not buffered backlog.

Implementation used here:
- `relay_sender.py` enforces one-in-flight.
- `ws_relay_callbacks.py` clears the gate on binary receive and disconnect.
- `relay_sender.py` clears stale in-flight state after timeout.

Why:
- This avoids lag accumulation and keeps the output visually live.


## 5. Timer-Driven Send Workflow

Prefer a CHOP-driven send pulse over ad hoc manual triggers when you need continuous streaming.

Implementation used here:
- `stream_timer` drives a changing `timer_fraction`.
- `stream_timer_exec` is a `chopexecuteDAT`.
- `send_exec.py` provides `onValueChange(...)`.
- `relay_sender.py` decides whether a frame should actually be sent.

Why:
- This isolates pacing to a single path.
- The sender gate handles backpressure.
- It is simpler than multiple competing execute paths.


## 6. Runpod Restart Recovery Workflow

Use this after the Runpod process or tunnel restarts.

Steps:
1. Verify local health:
   - `curl http://127.0.0.1:8000/health`
2. Reconnect/toggle `ws_relay.active`.
3. Clear `relay_in_flight`.
4. Leave the timer-driven send path armed.

Why:
- After server restart, TD may still be armed correctly but disconnected.
- The real blocker is usually tunnel/socket reachability, not the sender logic.


## 7. Script TOP Decoder Workflow

For `output_frame`:
- keep `onGetCookLevel(scriptOp)`
- keep `onCook(scriptOp)`
- output 3-channel RGB arrays only
- use `cv2` decode in this environment

Why:
- 4-channel arrays caused `bad argument to internal function`.
- Missing `onGetCookLevel()` caused Script TOP callback failures.

