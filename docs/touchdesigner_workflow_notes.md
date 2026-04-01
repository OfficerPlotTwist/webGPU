# TouchDesigner Workflow Notes

## Prompt Table Count

- `prompt_table` includes a header row.
- Any logic that derives the number of prompts must use `prompt_table.numRows - 1`, not the raw table length and not a static parameter guess.
- `prompt_index_exec.py` already uses the correct rule:
  - `prompt_count = max(0, table.numRows - 1)`
  - data rows are addressed with `row = index + 1`

## Count CHOP Guardrail

- `prompt_index` is a `countCHOP` and its `limitmax` should stay aligned with the actual prompt-table data row count.
- Before changing prompt cycling logic, verify:
  - the count excludes the header row
  - modulo math uses the data-row count
  - any parameter expression driving `limitmax` references the current `prompt_table` row count correctly

## TD Debug Checklist

- For DAT tables, prefer `table.numRows` / `table.numCols` from Python over guessing from UI parameters.
- If a table has column headers, explicitly subtract one when converting row count into selectable entries.
- When a CHOP parameter is expression-driven from a DAT, verify the expression after restart; stale or broken parameter references are easy to miss.

## Workflow: Verify Operator Paths Before Using `.module`

- `op("relay_sender").module.send_latest_frame()` only works if `relay_sender` resolves from the current network context.
- In Textport or callbacks, a missing relative path returns `None`, which then fails as `'NoneType' object has no attribute 'module'`.
- Preferred workflow:
  - verify with `op("relay_sender")`
  - if needed, use the absolute path like `/project1/webGPU_Streamdiffusion/relay_sender`
  - only then call `.module`

## Workflow: TOP to CHOP Uses Parameter Reference, Not Always a Wire

- `toptoCHOP` may not be wired from the TOP in the way other operators are.
- In this project/build, the stable setup was:
  - set `topto1.par.top = "10_by_10_downscale"`
  - do not rely on a direct TOP wire into `toptoCHOP`
- If image sampling logic appears broken, verify the `top` parameter first.

## Workflow: Use `onceperframe` for CHOP Execute Triggers

- `chopexecuteDAT` on `everysample` created too much trigger pressure for this websocket stream.
- The stable convention here is:
  - `valuechange = True`
  - `freq = onceperframe`
- Use `everysample` only when you explicitly want per-sample callback pressure.

## Workflow: Sum CHOP Should Mark Dirty, Not Send Immediately

- Using `sum.r` as a direct send trigger caused send pressure, reconnect churn, and dropped replies.
- The stable TouchDesigner pattern for this stream is:
  - `stream_timer_exec` / `send_exec` marks the source as dirty
  - `stream_exec` performs paced sends on frame start
  - sender keeps only the latest pending frame
- For live streaming in TD, change detection should request work, not perform network sends immediately.

## Workflow: Reload File-Synced DATs After Script Changes

- Editing the repo file alone is not enough if the live TD DAT has not reloaded.
- After changing a file-synced DAT script, pulse `loadonstartpulse` or otherwise force reload for:
  - `relay_sender`
  - `ws_relay_callbacks`
  - execute DATs that load from disk
- If behavior looks like old code is still running, assume the DAT did not reload yet.

## Workflow: Rebuild Lost Live Wiring After TD Restart

- Repo file changes persist; live network rewiring may not.
- After a TD crash/reopen, verify live operator settings instead of assuming the network still matches the repo intent.
- In this project the common checks are:
  - `stream_timer_exec` target CHOP/channel/freq
  - `relay_sender` file-sync path
  - existence of helper operators like `sum`, `10_by_10_downscale`, `topto1`

## Workflow: WebsocketDAT Stability Depends on TD Trigger Discipline

- Repeated websocket reconnects were not solved by server changes alone.
- TouchDesigner-side trigger discipline matters:
  - avoid flooding the websocket from change callbacks
  - keep one persistent connection
  - prefer paced sends and reply-driven flow control
- If Runpod logs show `websocket_closed` followed immediately by a new accepted connection, inspect TD trigger/reconnect behavior before assuming backend failure.
