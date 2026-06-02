# NevernessTheEverness Team Screen L

## Purpose

This pack targets the running Neverness To Everness client and performs one
local menu-hotkey input: press `L` once while the client is already on the
normal world view.

## Target

- Process: `HTGame.exe`
- Window title contains: `NTE`
- Input mode: `background_window_messages`

## Current Verification Boundary

- The pack assumes the operator has already placed the client on the world
  view.
- The pack does not yet include a visual team-screen marker.
- During this test session, operator review of the target preview is still
  required because the live runner can otherwise report `success` as soon as
  the input call returns.

## Timing Finding

The key issue for this pack turned out to be input dwell time, not only focus
or delivery method.

- A zero-duration `press_key` tap could be too short for the NTE client to
  observe reliably.
- Holding the same key for about `0.1s` gave the game enough time to sample the
  key state and react.
- The live adapter now gives `press_key` a short default dwell, and the profile
  can still use `hold_key` when a longer hold is needed.

## Known Limitations

- Background input requires the runner or dashboard to use the same Windows
  privilege level as the NTE client.
- This pack is only for local operator-approved UI testing and does not include
  gameplay automation.
