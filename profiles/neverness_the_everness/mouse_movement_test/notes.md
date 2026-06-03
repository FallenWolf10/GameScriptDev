# NevernessTheEverness Mouse Movement Test

## Purpose

This pack targets the running Neverness To Everness client and performs one
foreground mouse movement to test the new camera-input action path.

## Target

- Process: `HTGame.exe`
- Window title contains: `NTE`
- Input mode: `foreground`

The pack assumes the client is already on a safe in-world screen. It recenters
the cursor inside the target window, applies one small rightward relative mouse
movement, then waits briefly.

## Current Verification Boundary

- The profile does not include a visual confirmation anchor, so the runner will
  report success when the mouse movement action completes.
- Because this is a foreground mouse action, the operator should keep the NTE
  client focused and visually confirm the camera moved as expected.

## Known Limitations

- Mouse-look actions currently require foreground focus.
- This pack is only for local operator-approved camera-input testing and does
  not include gameplay automation.
