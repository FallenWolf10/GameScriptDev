# NevernessTheEverness Repeat F Key

This pack repeatedly taps `F` against the NevernessTheEverness client using the
repo's built-in `start_continuous_input` action.

## Behavior

- Starts one continuous `press_key` action named `repeat_f_key`
- Taps `F` every `0.2` seconds
- Uses a `0.1` second key-down dwell per tap
- Repeats a `55` second keep-alive wait loop for as long as the run is active
- Uses `background_window_messages` for live input delivery

## Stop Model

- There is no pack-local hotkey stop in the current runner
- Stop the run from the terminal or dashboard when you want input to end
- Dashboard dry runs for this pack are expected to be stopped manually by the operator
- The runner should release active continuous inputs when the run exits

## Review Notes

- This pack intentionally skips screen anchors because the request was only to
  repeat `F`
- The `F` input uses `background_window_messages`, so foreground focus is not
  required for key delivery
- Confirm the target process, title match, and background input behavior before
  live use
