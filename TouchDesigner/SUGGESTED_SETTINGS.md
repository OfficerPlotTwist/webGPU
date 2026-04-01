Suggested `settings.md` guidance for future TD MCP / TouchDesigner-assisted work on this project.

## Recommended additions

### 1. Callback Contract Rule

Always verify and preserve built-in TouchDesigner callback function names/signatures for the specific operator type before editing callback scripts.

Examples:
- `scriptTOP`:
  - `onGetCookLevel(scriptOp)`
  - `onCook(scriptOp)`
- `websocketDAT`:
  - do not assume signatures from other DATs
  - verify against live docs / `td_python_api.json`


### 2. File-Backed DAT Rule

When a live DAT is sourced from a repo file:
- edit the repo file first
- reload the DAT from file
- verify the live DAT text matches the file before concluding the fix did not work


### 3. Binary WebSocket Diagnostics Rule

For websocket image-return systems, always add explicit receive diagnostics during bring-up:
- payload size
- payload prefix hex
- base64 length or decode success marker
- receive timestamp

Reason:
- text `frame.result` can succeed even while binary receive is still broken.


### 4. Streaming Architecture Rule

For live diffusion:
- prefer one-in-flight latest-frame streaming
- do not queue source frames
- prefer backpressure over buffering

Reason:
- buffering causes output lag and makes live visuals feel stale.


### 5. Continuous Send Rule

Prefer a single timer/CHOP-driven pulse path for continuous sending.

Recommended pattern:
- timer/CHOP pulse
- CHOP Execute DAT with `onValueChange(...)`
- sender module performs:
  - in-flight gating
  - FPS limit
  - stale timeout recovery

Avoid:
- multiple simultaneous execute paths
- mixing frame-start execute DATs and timer CHOP paths unless there is a clear reason


### 6. Runpod Recovery Rule

When the remote server is restarted:
- verify local forwarded HTTP health first
- only then debug the TD websocket

Reason:
- many apparent TD reconnect failures were actually tunnel/server availability issues.


### 7. Decoder Output Rule

For Script TOP image output in this project:
- decode with `cv2`
- emit RGB arrays
- avoid 4-channel `copyNumpyArray()` output unless validated for the exact build


### 8. Config Merge Rule

When multiple TD controls modify session config:
- build the next config from current status/state
- do not rebuild from defaults on every update

Reason:
- prompt changes and denoise-step changes can overwrite each other if each starts from defaults.


## Proposed wording for an actual settings file

If these rules are later merged into a real `settings.md`, keep them brief and operational:

- Verify operator-specific TouchDesigner callback signatures before editing callback files.
- Treat repo-backed DAT files as source of truth and reload the DAT after edits.
- For websocket image return, instrument binary receive explicitly during bring-up.
- Prefer one-in-flight latest-frame streaming for live diffusion systems.
- Use a single timer/CHOP send path with sender-side backpressure and timeout recovery.
- After Runpod restart, verify forwarded local health before debugging TD reconnect behavior.
