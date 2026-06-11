# NevernessTheEverness Pink Button Paste Loop

## Purpose

This pack repeatedly sends `Ctrl+V`, then clicks the pink confirm button area
visible in the provided 1280x720 screenshot.

## Target

- Process: `HTGame.exe`
- Window title contains: `NTE`
- Input mode: `background_window_messages`

The pack assumes the game is already sitting on the same posting dialog each
time the loop runs. It does not verify screen state before sending input.

## Region Assumption

- `regions.pink_confirm_button` is tuned to the lower-right pink button in the
  provided screenshot
- Current rectangle: `x: 1088`, `y: 625`, `width: 159`, `height: 35`
- The runner clicks the center of that rectangle

If the click lands too far left, right, high, or low in live testing, adjust
that region only; the rest of the pack can stay the same.

## Loop Behavior

- Presses `Ctrl+V`
- Waits `0.2` seconds
- Clicks the pink confirm button region
- Waits `0.35` seconds
- Repeats until the operator stops the run

## Stop Model

- There is no profile-local stop hotkey
- Stop the run from the CLI or dashboard when you want the loop to end
- `manual_stop_is_dry_run_success` is enabled because manual stop is the normal
  expected outcome for this infinite loop pack
