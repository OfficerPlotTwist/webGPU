# TouchDesigner Operators

Create these operators in your TouchDesigner project:

- `webSocket DAT` named `ws_relay`
- callback `DAT` named `ws_relay_callbacks`
- `Text DAT` named `latest_frame_b64`
- `Text DAT` named `latest_frame_meta`
- `Table DAT` named `relay_status`
- sender `DAT` named `relay_sender`
- `CHOP Execute DAT` named `send_exec`
- `Script TOP` named `output_frame`
- callback `DAT` for the Script TOP named `output_frame_callbacks`

Paste the matching files from this folder into operators with the same names:

- `ws_relay_callbacks.py`
- `relay_sender.py`
- `send_exec.py`
- `output_frame_callbacks.py`

Set `ws_relay` to:

```text
ws://<RUNPOD-IP>:8000/ws/show-main
```

Drive `send_exec` from a timer or pulse source at about `4 FPS`.
